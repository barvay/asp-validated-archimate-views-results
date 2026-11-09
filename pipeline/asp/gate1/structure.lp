% Gate 1: structural checks on the filtered items. Model- and rulebook-independent.
% Input: model facts (element/3, relation/4) + keep_element/1, keep_relation/1.
% Output: violation(Code, Ids), message(Code, Text).

has_element :- keep_element(_).
violation("EMPTY-VIEW", ()) :- not has_element.
message("EMPTY-VIEW", "The view keeps no element.").

violation("UNKNOWN-ELEMENT", (E,)) :- keep_element(E), not element(E,_,_).
message("UNKNOWN-ELEMENT", "Kept element id does not exist in the model (it may be a relation id or a typo).").

violation("UNKNOWN-RELATION", (R,)) :- keep_relation(R), not relation(R,_,_,_).
message("UNKNOWN-RELATION", "Kept relation id does not exist in the model (it may be an element id or a typo).").

violation("DANGLING-RELATION", (R,S)) :- keep_relation(R), relation(R,_,S,_), not keep_element(S).
violation("DANGLING-RELATION", (R,T)) :- keep_relation(R), relation(R,_,_,T), not keep_element(T).
message("DANGLING-RELATION", "Kept relation has an endpoint that is not kept: keep the endpoint or drop the relation.").
