% Gate 3c: nesting shows a nesting relation (Composition, Aggregation, or a nesting specialization),
% so the diagram draws no edge for it.
% Input: model facts + keep_relation/1 + inside/2 (2_layout.lp) + edge/3 (parsed from 3_view.drawio).
% A kept nesting relation S -> T is a nested relation when T is directly inside S
% (inside(T, S), same direction as in the model). correspondence.lp exempts it from MISSING-EDGE.
% nesting_relation/1: asp/common/nesting.lp.

nested_relation(R) :- keep_relation(R), relation(R,_,S,C), nesting_relation(R), inside(C,S).

violation("NESTED-EDGE", (R,)) :- nested_relation(R), edge(R,_,_).
message("NESTED-EDGE", "This Composition/Aggregation relation is shown by nesting its target inside its source (inside/2 in the layout). Do not draw an edge for it.").
