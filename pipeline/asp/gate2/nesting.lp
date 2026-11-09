% Gate 2b: nesting is ArchiMate notation for a relation, so it must not claim one the view does not have.
% Input: model facts (relation/4) + keep_relation/1 (1_filter.lp) + band/2, inside/2 (2_layout.lp)
%        + nesting_relation/1 (asp/common/nesting.lp).
% inside(A, B) is allowed when B is an `other` element (Grouping, Location: free containers), or when
% a kept nesting relation (Composition, Aggregation, or a nesting specialization) runs from the
% container B to A. Direct nesting only: every step of a nesting chain is checked on its own.

nests(A,B) :- inside(A,B), keep_relation(R), relation(R,_,B,A), nesting_relation(R).
violation("NESTING-WITHOUT-RELATION", (A,B)) :- inside(A,B), not band(B,other), not nests(A,B).
message("NESTING-WITHOUT-RELATION", "Nesting shows a relation: inside(A, B) needs a kept Composition or Aggregation relation from the container B to A (a relation in the other direction, of another type or not kept does not count), or B must be a Grouping/Location (`other`). Place the two elements side by side (left_of/above) instead (element, container).").
