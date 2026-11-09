# ASP fact schema

The facts exchanged between the steps of the pipeline. The schema is provisional and may still
change; a change goes here first, then into `scripts/export_facts.py`, the prompts and `asp/`, and
`data/model/model_facts.lp` is regenerated. Identifiers are the Archi XML `id`s.

All identifiers and names are ASP **strings** (double-quoted), because ArchiMate ids contain
characters such as `-`.

## Model facts (input, `data/model/model_facts.lp`)

```prolog
element(Id, Type, Name).            % Type: ArchiMate base type, e.g. "ApplicationComponent"
specialization(Id, Spec).           % specialization (Archi profile), e.g. "storefront"
relation(Id, Type, Source, Target). % Type: ArchiMate relation type, e.g. "Flow"
rel_specialization(Id, Spec).       % of a relation, e.g. "nightly_batch"
property(Id, Key, Value).           % optional, only properties a check needs
access_type(Id, Mode).              % Access relation: "write" | "read" | "access" | "readwrite"
directed(Id).                       % Association relation drawn as directed

% Predefined views: every diagram of the model
view(V, Name).                      % V: the Archi id of the diagram; Name: the diagram name
view_documentation(V, Text).        % the diagram's documentation, if it has one
view_element(V, E).                 % element on the view
view_relation(V, R).                % relation on the view: a connection, or shown by nesting
                                    % (a relation from the container to the nested element)
view_inside(V, E, C).               % E is drawn directly inside C on the view
```

Produced by `python3 scripts/export_facts.py data/model/model.archimate --out <file>`:
ids are Archi XML ids, `Type` is the Archi type without the `Relationship` suffix, `Spec` is the name
of the Archi specialization (profile). Exported properties: none (`EXPORTED_PROPERTIES` in
`export_facts.py`). `access_type` comes from the Archi `accessType` attribute (absent = write),
`directed` from `directed="true"`. Every ArchiMate diagram is exported as a
view; notes and other diagram objects are not.

## Step 1 output (`1_filter.lp`, filtering agent)

```prolog
keep_element("id-...").
keep_relation("id-...").
use_view("id-...").  % instead: the intent asks for exactly this predefined view
```

For a `use_view`, `scripts/run.py` rewrites the file as `use_view` plus `keep_element`/`keep_relation`
for every `view_element`/`view_relation` of the view; gate 1 (`asp/gate1/views.lp`) checks the 1:1
correspondence.

## Step 2 output (`2_layout.lp`, layout agent)

```prolog
band(E, B).      % B: motivation | business | application | technology | other
left_of(A, B).
above(A, B).
inside(A, B).
```

Agent files may contain only their allowed predicates, one fact per line, `%` comments allowed.
`pipeline.py` rejects anything else before Clingo runs (`SYNTAX`), so an agent cannot change the
check logic.

## Step 3 output, parsed (`3_view_facts.lp`, written by `pipeline.py` from `3_view.drawio`)

```prolog
cell(Id, X, Y, W, H).      % vertex, absolute integer coordinates (y grows downwards)
cell_label(Id, Text).      % visible label text of a vertex on one line (lines joined with a space)
cell_line(Id, N, Text).    % N-th visible line of a vertex label (split at <br>, <div>, <p>, newline)
cell_style(Id, Key, Value). % vertex fillColor / strokeColor / dashed, lower case (only the keys the style sets)
edge(Id, Source, Target).
edge_label(Id, Text).      % visible label text of an edge (its own value attribute)
edge_style(Id, Key, Value).  % edge style keys of the notation: startArrow, endArrow, startFill,
                             % endFill, dashed, dashPattern (only the keys the style sets)
duplicate_id(Id).
```

Label text: html tags removed, entities decoded, Unicode NFC, whitespace normalised (as in
`export_facts.py`), empty lines dropped.

Band frames are vertices with the reserved ids `band-motivation`, `band-business`,
`band-application` and `band-technology` (`asp/gate3/bands.lp`); every other vertex id is an element id.

## Gate output (rules in `asp/gate<N>/*.lp`)

```prolog
violation(Code, Ids).       % Code: string; Ids: tuple of strings/constants
message(Code, Text).        % English explanation of Code, in the same file as the rule
```
