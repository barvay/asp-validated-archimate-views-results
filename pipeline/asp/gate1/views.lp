% Gate 1b: a predefined view (use_view/1) is taken over 1:1 from the model: the filtered items are
% exactly the elements and relations of the model's view, nothing missing, nothing added.
% Input: model facts (view/2, view_element/2, view_relation/2) + use_view/1, keep_element/1, keep_relation/1.
% run.py writes the keep_ facts of a use_view itself; these rules state the contract.

violation("UNKNOWN-VIEW", (V,)) :- use_view(V), not view(V,_).
message("UNKNOWN-VIEW", "use_view names a view that is not a predefined view of the model; use an id of the view catalogue.").

violation("MULTIPLE-VIEWS", (V1,V2)) :- use_view(V1), use_view(V2), V1 < V2.
message("MULTIPLE-VIEWS", "Only one predefined view can be taken over.").

violation("VIEW-MISSING-ELEMENT", (V,E)) :- use_view(V), view(V,_), view_element(V,E), not keep_element(E).
message("VIEW-MISSING-ELEMENT", "An element of the predefined view is not kept (view, element).").
violation("VIEW-EXTRA-ELEMENT", (V,E)) :- use_view(V), view(V,_), keep_element(E), not view_element(V,E).
message("VIEW-EXTRA-ELEMENT", "A kept element is not on the predefined view (view, element).").

violation("VIEW-MISSING-RELATION", (V,R)) :- use_view(V), view(V,_), view_relation(V,R), not keep_relation(R).
message("VIEW-MISSING-RELATION", "A relation of the predefined view is not kept (view, relation).").
violation("VIEW-EXTRA-RELATION", (V,R)) :- use_view(V), view(V,_), keep_relation(R), not view_relation(V,R).
message("VIEW-EXTRA-RELATION", "A kept relation is not on the predefined view (view, relation).").
