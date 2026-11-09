% Gate 2: consistency of the abstract layout. Model-independent.
% Input: model facts + keep_element/1, keep_relation/1 + band/2, left_of/2, above/2, inside/2.
% Meaning: left_of(A,B) A is left of B; above(A,B) A is above B; inside(A,B) A is nested in B.

% --- every kept element is placed in exactly one valid band, matching its ArchiMate layer
placed(E) :- band(E,_).
violation("UNPLACED-ELEMENT", (E,)) :- keep_element(E), not placed(E).
message("UNPLACED-ELEMENT", "Kept element has no band/2 fact.").

violation("MULTIPLE-BANDS", (E,B1,B2)) :- band(E,B1), band(E,B2), B1 < B2.
message("MULTIPLE-BANDS", "Element is placed in more than one band.").

violation("UNKNOWN-BAND", (E,B)) :- band(E,B), not band_name(B).
message("UNKNOWN-BAND", "Unknown band; use motivation, business, application, technology or other.").

violation("WRONG-BAND", (E,B,X)) :- band(E,B), band_name(B), keep_element(E), element(E,T,_), type_band(T,X), B != X.
message("WRONG-BAND", "Element is in a band that does not match its ArchiMate layer (element, given band, expected band).").

% --- only kept elements may be referenced
ref(E) :- band(E,_).
ref(A;B) :- left_of(A,B).
ref(A;B) :- above(A,B).
ref(A;B) :- inside(A,B).
violation("NOT-KEPT", (E,)) :- ref(E), not keep_element(E).
message("NOT-KEPT", "Layout refers to an id that is not a kept element. Do not add or invent elements.").

% --- no self reference
violation("SELF-REFERENCE", ("left_of",A)) :- left_of(A,A).
violation("SELF-REFERENCE", ("above",A))   :- above(A,A).
violation("SELF-REFERENCE", ("inside",A))  :- inside(A,A).
message("SELF-REFERENCE", "An element is placed relative to itself.").

% --- no cycles (transitive closure); a pair on a cycle reaches each other
lt(A,B) :- left_of(A,B).
lt(A,C) :- lt(A,B), left_of(B,C).
ab(A,B) :- above(A,B).
ab(A,C) :- ab(A,B), above(B,C).
in(A,B) :- inside(A,B).
in(A,C) :- in(A,B), inside(B,C).
violation("CYCLE", ("left_of",A,B)) :- lt(A,B), lt(B,A), A < B.
violation("CYCLE", ("above",A,B))   :- ab(A,B), ab(B,A), A < B.
violation("CYCLE", ("inside",A,B))  :- in(A,B), in(B,A), A < B.
message("CYCLE", "The relation forms a cycle, so the elements cannot be placed (relation, two elements on the cycle).").

% --- nested elements cannot also be beside each other
nested(A,B) :- in(A,B).
nested(A,B) :- in(B,A).
violation("NESTED-AND-BESIDE", ("left_of",A,B)) :- nested(A,B), left_of(A,B).
violation("NESTED-AND-BESIDE", ("above",A,B))   :- nested(A,B), above(A,B).
message("NESTED-AND-BESIDE", "Two elements are nested in each other and also placed side by side or one above the other.").

% --- one direct parent (unless the parents are nested in each other: then declare only the innermost)
violation("MULTIPLE-PARENTS", (A,P1,P2)) :- inside(A,P1), inside(A,P2), P1 < P2.
message("MULTIPLE-PARENTS", "Element is directly inside two containers; keep only the innermost one.").

% --- the layout must respect the band order (other has no rank and is free)
rank(E,R) :- band(E,B), band_rank(B,R).
violation("ABOVE-AGAINST-BANDS", (A,B)) :- ab(A,B), rank(A,RA), rank(B,RB), RA > RB.
message("ABOVE-AGAINST-BANDS", "A is (transitively) above B, but B's band is higher (bands top to bottom: motivation, business, application, technology).").

violation("NESTED-ACROSS-BANDS", (A,B)) :- inside(A,B), rank(A,RA), rank(B,RB), RA != RB.
message("NESTED-ACROSS-BANDS", "An element is nested in a container of another band. Only `other` elements (e.g. Grouping, Location) may contain elements of other bands.").

% --- band frames: every element of a band is drawn inside its band's frame (asp/gate3/bands.lp), so an
% `other` element nested with band elements belongs to their frame, and only to one frame
violation("OTHER-ACROSS-BANDS", (C,A,B)) :- band(C,other), in(A,C), in(B,C), rank(A,RA), rank(B,RB), RA < RB.
message("OTHER-ACROSS-BANDS", "An `other` container (e.g. Grouping) holds elements of two bands (container, two elements). Each band is drawn in its own frame, so a container may hold elements of one band only.").

% frame of an `other` element: the band of its contents, or of the element it is nested in
frame_rank(E,R) :- rank(E,R).
frame_rank(C,R) :- band(C,other), in(A,C), rank(A,R).
frame_rank(C,R) :- band(C,other), in(C,P), frame_rank(P,R).
violation("OTHER-NESTED-ACROSS-BANDS", (A,C)) :- in(A,C), frame_rank(A,RA), frame_rank(C,RC), RA != RC, band(A,other).
violation("OTHER-NESTED-ACROSS-BANDS", (A,C)) :- in(A,C), frame_rank(A,RA), frame_rank(C,RC), RA != RC, band(C,other).
message("OTHER-NESTED-ACROSS-BANDS", "Nesting through an `other` element puts elements of two bands into one another (element, container). Each band is drawn in its own frame.").

% --- implied contradictions: a container's position holds for everything inside it, and the band
% order (frames, also of `other` elements) puts every box of a higher band above every box of a lower
% one. Effective relations: left_of/above from each fact to all descendants of both ends, plus the
% band order. A fact is reported when the effective relations also put the other end before it;
% contradictions that need neither nesting nor frames are reported by CYCLE, NESTED-AND-BESIDE and
% ABOVE-AGAINST-BANDS above. Sound, not complete: a contradiction that forces boxes to overlap is
% only found by gate 3 (OVERLAP).
self_or_in(X,X) :- ref(X).
self_or_in(X,P) :- in(X,P).

eff_lt(X,Y) :- left_of(P,Q), self_or_in(X,P), self_or_in(Y,Q).
eff_lt(X,Z) :- eff_lt(X,Y), eff_lt(Y,Z).
eff_ab(X,Y) :- above(P,Q), self_or_in(X,P), self_or_in(Y,Q).
eff_ab(X,Y) :- frame_rank(X,RX), frame_rank(Y,RY), RX < RY.
eff_ab(X,Z) :- eff_ab(X,Y), eff_ab(Y,Z).

violation("IMPLIED-CYCLE", ("left_of",P,Q)) :- left_of(P,Q), self_or_in(X,P), self_or_in(Y,Q), eff_lt(Y,X),
                                               not lt(Q,P), not nested(P,Q).
violation("IMPLIED-CYCLE", ("above",P,Q))   :- above(P,Q), self_or_in(X,P), self_or_in(Y,Q), eff_ab(Y,X),
                                               not ab(Q,P), not nested(P,Q), not against_bands(P,Q).
% the fact lies on an above chain that ABOVE-AGAINST-BANDS reports
ab_or_self(X,X) :- ref(X).
ab_or_self(X,Y) :- ab(X,Y).
against_bands(P,Q) :- above(P,Q), ab_or_self(A,P), ab_or_self(Q,B), rank(A,RA), rank(B,RB), RA > RB.
message("IMPLIED-CYCLE", "This fact cannot hold together with the others: a container's left_of/above also holds for everything inside it, and every box of a higher band (or of an `other` element in that band's frame) is above every box of a lower band, so the elements end up on both sides of each other (relation, the fact's two elements). Fix this fact or the facts about the containers involved.").
