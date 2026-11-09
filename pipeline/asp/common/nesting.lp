% Relations the pipeline shows by nesting the target inside the source (gate 2:
% NESTING-WITHOUT-RELATION, gate 3: NESTED-EDGE, MISSING-EDGE).
% ArchiMate types: ArchiMate 3.1 also allows nesting for Assignment, Realization and Specialization;
% the pipeline uses it only for these two.
nesting_type("Composition").
nesting_type("Aggregation").
% Relation specializations that a project's views show by nesting: one fact
% nesting_specialization("<name>") each. None here. A project that adds one names it in the prompts
% too (layout, drawio, judge), where they list the relations shown by nesting.
#defined nesting_specialization/1.

nesting_relation(R) :- relation(R,T,_,_), nesting_type(T).
nesting_relation(R) :- rel_specialization(R,S), nesting_specialization(S).
