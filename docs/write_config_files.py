"""Write docs/config_files.md (every field of every config file, from the config models)
and docs/images/config_names.svg (how the files refer to each other by name).

Each file is shown as a YAML example in which every field it accepts appears
once, with a comment above it: required or its default, the allowed values and
limits, and the field's ``description``. The values are the field's
``examples`` (or its default). Run it after changing a model in
``microcircuit_lab/config/``; ``tests/test_config_reference.py`` fails while
the page is out of date. It stops on a field without a ``description`` and on an
example that is not a valid file.

    python docs/write_config_files.py
"""

from __future__ import annotations

import re
import sys
import textwrap
import types
import typing
from html import escape
from pathlib import Path

import annotated_types
import yaml
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from microcircuit_lab.config.background_inputs import BackgroundInputsFile
from microcircuit_lab.config.connectivity import ConnectivityFile
from microcircuit_lab.config.network import NetworkManifest
from microcircuit_lab.config.neurons import NeuronParams, NeuronsFile
from microcircuit_lab.config.populations import PopulationsFile
from microcircuit_lab.config.reference import ReferenceConfig
from microcircuit_lab.config.scaling import ScalingConfig
from microcircuit_lab.config.simulation import SimulationConfig
from microcircuit_lab.config.stimuli import StimuliFile

PAGE = Path(__file__).resolve().parent / "config_files.md"
IMAGE = PAGE.parent / "images" / "config_names.svg"
WIDTH = 88

# (file, model, what the file is for)
FILES = [
    ("network.yaml", NetworkManifest, "Names the file of each part. The names below are the usual ones."),
    ("populations.yaml", PopulationsFile, "The populations: size, neuron and initial state."),
    ("neurons.yaml", NeuronsFile, "The neuron models, by name. Several populations can share one."),
    ("connectivity.yaml", ConnectivityFile, "The connections between populations."),
    ("background_inputs.yaml", BackgroundInputsFile, "The always-on Poisson input of each population."),
    ("stimuli.yaml", StimuliFile, "Optional: inputs for an experiment, applied as written (never scaled)."),
    ("scaling.yaml", ScalingConfig, "How to downscale the network; see \"Scaling a network\" in the README."),
    ("reference.yaml", ReferenceConfig, "Published values to compare with, and to compensate a scaled network."),
]
SIMULATION = ("simulation/<name>.yaml", SimulationConfig, "How to run: duration, seed, threads, what to record and save.")

# An example key for the fields that are a mapping keyed by name.
KEY_EXAMPLES = {"neurons": "excitatory", "background_inputs": "L23_E"}

# The picture: excerpts of the toy network, population names in blue and
# neuron names in orange. In the lines, [E] marks a population name, {excitatory}
# a neuron name, and \\[ \\] a literal bracket.
POPULATION_COLOR, NEURON_COLOR = "#1a5fb4", "#c64600"
EXCERPTS = [
    ("neurons.yaml", "defines the neuron names", NEURON_COLOR, [
        "neurons:", "  {excitatory}:", "    model: iaf_psc_exp", "    parameters: …",
        "  {inhibitory}:", "    model: iaf_psc_exp", "    parameters: …"]),
    ("populations.yaml", "defines the population names", POPULATION_COLOR, [
        "populations:", "  - name: [E]", "    size: 800", "    neuron: {excitatory}",
        "  - name: [I]", "    size: 200", "    neuron: {inhibitory}"]),
    ("connectivity.yaml", "uses population names", None, [
        "connections:", "  - source: [E]", "    target: [I]", "    n_synapses: 64000",
        "    weight: …", "    delay: …"]),
    ("background_inputs.yaml", "uses population names", None, [
        "background_inputs:", "  [E]:", "    rate: 8.0", "    weight: …",
        "  [I]:", "    rate: 8.0", "    weight: …"]),
    ("stimuli.yaml", "uses population names", None, [
        "stimuli:", "  - type: dc", "    targets: \\[[E]\\]", "    amplitude: 200.0",
        "    start: 500.0", "    stop: 600.0"]),
    ("reference.yaml", "uses population names", None, [
        "full_mean_rates:", "  [E]: 20.0", "  [I]: 20.0"]),
]
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
TEXT, MUTED, BORDER = "#1f2328", "#59636e", "#8c959f"

LIMITS = {
    annotated_types.Gt: ("gt", ">"),
    annotated_types.Ge: ("ge", "≥"),
    annotated_types.Lt: ("lt", "<"),
    annotated_types.Le: ("le", "≤"),
}


def _value(value) -> str:
    """A value as it would be written in a YAML file, on one line."""
    text = yaml.safe_dump(value, default_flow_style=True, sort_keys=False, width=1000)
    return text.removesuffix("\n...\n").strip()


def _number(value) -> str:
    """A limit as people write it: 0 rather than 0.0."""
    return str(int(value)) if float(value).is_integer() else str(value)


def _unwrap(annotation):
    """The annotation without `| None`, and whether None was allowed."""
    args = typing.get_args(annotation)
    if typing.get_origin(annotation) in (typing.Union, types.UnionType) and type(None) in args:
        rest = [arg for arg in args if arg is not type(None)]
        return rest[0], True
    return annotation, False


def _kind(annotation) -> str:
    """A short name for the kind of value a field takes."""
    annotation, _ = _unwrap(annotation)
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin is typing.Literal:
        return "one of " + " | ".join(str(arg) for arg in args)
    if origin is list:
        return "list of " + {str: "names", float: "numbers", int: "integers"}.get(args[0], "entries")
    if origin is dict:
        return "mapping"
    return {str: "text", int: "integer", float: "number", bool: "true or false", Path: "path"}.get(
        annotation, ""
    )


def _comment(field: FieldInfo, *, tag: bool = False) -> str:
    """The comment above a field: required or default · kind and limits · description."""
    parts = []
    if tag:
        parts.append("required · selects the fields below")
    elif field.is_required():
        parts.append("required")
    else:
        default = field.get_default(call_default_factory=True)
        if default is None:
            parts.append("optional")
        elif isinstance(default, (dict, list)) and not default:
            parts.append("optional, default empty")
        elif not isinstance(default, BaseModel):
            parts.append(f"optional, default {_value(default)}")
        else:
            parts.append("optional")
    kind = "" if tag else _kind(field.annotation)
    limits = [
        f"{LIMITS[type(m)][1]} {_number(getattr(m, LIMITS[type(m)][0]))}"
        for m in field.metadata
        if type(m) in LIMITS
    ]
    values = " ".join([kind, *limits]).strip()
    lengths = [f"at least {m.min_length}" for m in field.metadata if isinstance(m, annotated_types.MinLen)]
    if values or lengths:
        parts.append(", ".join(part for part in [values, *lengths] if part))
    if field.description:
        parts.append(field.description)
    return " · ".join(parts)


def _comment_lines(text: str, indent: str) -> list[str]:
    return textwrap.wrap(
        text,
        width=WIDTH,
        initial_indent=f"{indent}# ",
        subsequent_indent=f"{indent}#   ",
        break_on_hyphens=False,
    )


def _example(name: str, field: FieldInfo):
    if field.examples:
        return field.examples[0]
    default = field.get_default(call_default_factory=True)
    if default is PydanticUndefined:
        raise ValueError(f"{name}: a required field needs `examples=[...]`")
    return default


def _model_of(annotation):
    annotation, _ = _unwrap(annotation)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


class _Writer:
    def __init__(self) -> None:
        # Nested models already written in full, and where.
        self.seen: dict[type, str] = {}
        self.file = ""

    def model(self, model: type[BaseModel], indent: str, *, tag: str | None = None) -> list[str]:
        """Every field of a model, each with its comment."""
        lines = []
        # The tag goes first: it says which fields follow.
        fields = sorted(model.model_fields.items(), key=lambda item: item[0] != tag)
        for name, field in fields:
            if name == tag:
                lines += _comment_lines(_comment(field, tag=True), indent)
                lines.append(f"{indent}{name}: {_value(field.default)}")
            else:
                if not field.description:
                    raise ValueError(f"{model.__name__}.{name}: add `description=...`")
                lines += _comment_lines(_comment(field), indent)
                lines += self.field(name, field, indent)
        return lines

    def field(self, name: str, field: FieldInfo, indent: str) -> list[str]:
        annotation, _ = _unwrap(field.annotation)
        origin, args = typing.get_origin(annotation), typing.get_args(annotation)
        inner = indent + "  "

        if origin is list and typing.get_origin(args[0]) is typing.Annotated:
            # A list of several kinds of entry, told apart by a tag field.
            union, info = typing.get_args(args[0])
            lines = [f"{indent}{name}:"]
            for variant in typing.get_args(union):
                lines += _comment_lines(f"{variant.__doc__.strip().splitlines()[0]}", inner)
                lines += self._list_item(self.model(variant, inner + "  ", tag=info.discriminator), inner)
            return lines
        if origin is list and _model_of(args[0]):
            return [f"{indent}{name}:", *self._list_item(self.model(args[0], inner + "  "), inner)]
        if origin is dict and _model_of(args[1]):
            key = KEY_EXAMPLES[name]
            return [f"{indent}{name}:", f"{inner}{key}:", *self.model(args[1], inner + "  ")]
        if _model_of(annotation) is NeuronParams:
            values = _example(name, field)
            return [f"{indent}{name}:", *(f"{inner}{key}: {_value(v)}" for key, v in values.items())]
        if model := _model_of(annotation):
            if model in self.seen:
                example = {key: _example(key, f) for key, f in model.model_fields.items() if f.is_required()}
                return [f"{indent}{name}: {_value(example)}   # all fields as in {self.seen[model]}"]
            self.seen[model] = self.file
            return [f"{indent}{name}:", *self.model(model, inner)]
        if origin is dict and _example(name, field):
            return [f"{indent}{name}:", *(f"{inner}{key}: {_value(v)}" for key, v in _example(name, field).items())]
        value = _example(name, field)
        return [f"{indent}{name}: {_value(value) if value is not None else ''}".rstrip()]

    @staticmethod
    def _list_item(lines: list[str], indent: str) -> list[str]:
        """Turn the lines of one entry into a list item: `- ` before its first field."""
        first = next(i for i, line in enumerate(lines) if not line.lstrip().startswith("#"))
        comments = [line[2:] for line in lines[:first]]
        return [*comments, f"{indent}- {lines[first][len(indent) + 2:]}", *lines[first + 1:]]


def _colored(line: str) -> str:
    """One excerpt line as SVG text, with the marked names in color."""
    out = []
    for part in re.split(r"(\\\[|\\\]|\[[^\]]+\]|\{[^}]+\})", line):
        if part in ("\\[", "\\]"):
            out.append(escape(part[1]))
        elif part.startswith("["):
            out.append(f'<tspan fill="{POPULATION_COLOR}" font-weight="700">{escape(part[1:-1])}</tspan>')
        elif part.startswith("{"):
            out.append(f'<tspan fill="{NEURON_COLOR}" font-weight="700">{escape(part[1:-1])}</tspan>')
        else:
            out.append(escape(part))
    return "".join(out)


def names_svg() -> str:
    """The picture: one box per file, three per row, the shared names in color."""
    width, columns, gap, pad, line, head = 880, 3, 20, 20, 21, 52
    box_width = (width - 2 * pad - (columns - 1) * gap) / columns
    parts = [
        f'<text x="{pad}" y="{pad + 16}" font-family="{SANS}" font-size="15" fill="{TEXT}">'
        'Files refer to each other <tspan font-weight="700">by name</tspan>. Same color = same name:</text>',
        f'<text x="{pad}" y="{pad + 40}" font-family="{SANS}" font-size="15" fill="{TEXT}">'
        f'<tspan fill="{POPULATION_COLOR}" font-weight="700">E, I</tspan> population names   ·   '
        f'<tspan fill="{NEURON_COLOR}" font-weight="700">excitatory, inhibitory</tspan> neuron names</text>',
    ]
    y = pad + 70
    for row in range(0, len(EXCERPTS), columns):
        boxes = EXCERPTS[row:row + columns]
        height = head + 18 + max(len(lines) for *_, lines in boxes) * line
        for column, (name, role, color, lines) in enumerate(boxes):
            x = pad + column * (box_width + gap)
            stroke, stroke_width = (color, 2.5) if color else (BORDER, 1.2)
            parts += [
                f'<rect x="{x:g}" y="{y}" width="{box_width:g}" height="{height}" rx="8" fill="#ffffff" '
                f'stroke="{stroke}" stroke-width="{stroke_width}"/>',
                f'<path d="M{x:g} {y + head}h{box_width:g}" stroke="{stroke}" stroke-width="1"/>',
                f'<text x="{x + 14:g}" y="{y + 22}" font-family="{MONO}" font-size="15" font-weight="700" '
                f'fill="{TEXT}">{escape(name)}</text>',
                f'<text x="{x + 14:g}" y="{y + 41}" font-family="{SANS}" font-size="13" '
                f'fill="{color or MUTED}">{escape(role)}</text>',
            ]
            parts += [
                f'<text x="{x + 14:g}" y="{y + head + 22 + i * line}" font-family="{MONO}" font-size="14" '
                f'fill="{TEXT}" xml:space="preserve">{_colored(text)}</text>'
                for i, text in enumerate(lines)
            ]
        y += height + gap
    height = y - gap + pad
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        'aria-label="The config files of a network refer to each other by name">\n'
        f'<rect width="{width}" height="{height}" rx="12" fill="#f6f8fa"/>\n'
        + "\n".join(parts)
        + "\n</svg>\n"
    )


def render() -> str:
    writer = _Writer()
    sections = []
    for file, model, intro in [*FILES, SIMULATION]:
        writer.file = file
        body = "\n".join(writer.model(model, ""))
        # The example must itself be a valid file.
        model.model_validate(yaml.safe_load(body))
        sections.append(f"### {file}\n\n{intro}\n\n```yaml\n{body}\n```")
    network, simulation = sections[: len(FILES)], sections[len(FILES):]
    return "\n".join(
        [
            "# Config files",
            "",
            "<!-- Written by docs/write_config_files.py from microcircuit_lab/config/; "
            "do not edit by hand. -->",
            "",
            "Every field each config file accepts, as a YAML example. The comment above a field says "
            "whether it is required (or its default), the values it takes, and what it means. "
            "A mistake is reported when the network is read, naming the file and the field.",
            "",
            "## A network: `configs/network/<name>/`",
            "",
            "One folder per network, one file per part. A population is named once, in "
            "`populations.yaml`, and the other files use that name; a neuron likewise, in "
            "`neurons.yaml`. (`network.yaml` lists the files; `scaling.yaml` uses no names.)",
            "",
            "![The files of a network refer to each other by name](images/config_names.svg)",
            "",
            "What this means for a model:",
            "",
            "- **A population has one neuron entry.** Every neuron in it gets the same model and the "
            "same parameters; only the starting membrane potential differs (drawn from `V0_mean` "
            "and `V0_std`).",
            "- **Connections are set per pair of populations**: one entry for each source and "
            "target, with the number of synapses and the distributions their weights and delays "
            "are drawn from. Every connection uses the same rule (a fixed total number of "
            "synapses) and NEST's default synapse and receptor; several synapse models, "
            "receptors or rules for one pair (e.g. AMPA and NMDA) are not supported yet.",
            "- **So, for neurons with another model or other parameters, or wired differently, make "
            "a separate population.** In `configs/network/toy_stimulated/`, `E` (`iaf_psc_exp`) "
            "and `E_adex` (`aeif_cond_exp`) are two populations, each with its own connections.",
            "- **Several populations can share one neuron entry**, e.g. one `excitatory` entry "
            "for the excitatory populations of every layer.",
            "- **Names are only labels.** `E` does not make a population excitatory: the sign of "
            "its outgoing weights does.",
            "",
            "A small working example to copy: [`configs/network/toy/`](../configs/network/toy/).",
            "",
            "\n\n".join(network),
            "",
            "## Running it: `configs/simulation/`",
            "",
            "`microcircuit-lab run --network <name>` uses `configs/simulation/<name>.yaml`, "
            "or the defaults below when there is none.",
            "",
            "\n\n".join(simulation),
            "",
        ]
    )


def main() -> None:
    IMAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(render(), encoding="utf-8")
    IMAGE.write_text(names_svg(), encoding="utf-8")
    print(f"Wrote {PAGE} and {IMAGE}")


if __name__ == "__main__":
    sys.exit(main())
