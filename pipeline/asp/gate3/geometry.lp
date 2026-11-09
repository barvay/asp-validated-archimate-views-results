% Gate 3b: the coordinates satisfy the validated abstract layout, and boxes do not overlap.
% Input: band/2, left_of/2, above/2, inside/2 (2_layout.lp) + cell/5 (parsed from 3_view.drawio).
% Geometry (y grows downwards):
%   left_of(A,B): right edge of A <= left edge of B
%   above(A,B):   bottom edge of A <= top edge of B
%   inside(A,B):  box of A lies completely within box of B
%   bands:        every box of a higher band lies above every box of a lower band

violation("LEFT-OF-VIOLATED", (A,B)) :- left_of(A,B), cell(A,XA,_,WA,_), cell(B,XB,_,_,_), XA+WA > XB.
message("LEFT-OF-VIOLATED", "left_of(A,B) requires A's right edge (x+width) <= B's left edge (x).").

violation("ABOVE-VIOLATED", (A,B)) :- above(A,B), cell(A,_,YA,_,HA), cell(B,_,YB,_,_), YA+HA > YB.
message("ABOVE-VIOLATED", "above(A,B) requires A's bottom edge (y+height) <= B's top edge (y).").

contains(B,A) :- inside(A,B), cell(A,XA,YA,WA,HA), cell(B,XB,YB,WB,HB),
                 XA >= XB, YA >= YB, XA+WA <= XB+WB, YA+HA <= YB+HB.
violation("INSIDE-VIOLATED", (A,B)) :- inside(A,B), cell(A,_,_,_,_), cell(B,_,_,_,_), not contains(B,A).
message("INSIDE-VIOLATED", "inside(A,B) requires A's box to lie completely within B's box.").

% Band order: band_rank/2 from asp/common/archimate_layers.lp.
violation("BAND-ORDER-VIOLATED", (A,B)) :- band(A,BA), band(B,BB), band_rank(BA,RA), band_rank(BB,RB), RA < RB,
                                           cell(A,_,YA,_,HA), cell(B,_,YB,_,_), YA+HA > YB.
message("BAND-ORDER-VIOLATED", "A is in a higher band than B, so A's bottom edge must be <= B's top edge.").

% Boxes may overlap only if one is (transitively) inside the other.
anc(A,B) :- inside(A,B).
anc(A,C) :- anc(A,B), inside(B,C).
% Band frames (bands.lp) contain boxes by design and are checked there.
violation("OVERLAP", (A,B)) :- cell(A,XA,YA,WA,HA), cell(B,XB,YB,WB,HB), A < B, not frame_cell(A), not frame_cell(B),
                               XA < XB+WB, XB < XA+WA, YA < YB+HB, YB < YA+HA,
                               not anc(A,B), not anc(B,A).
message("OVERLAP", "Two boxes overlap although neither is inside the other.").
