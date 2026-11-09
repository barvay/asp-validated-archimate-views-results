% Gate 3e: every non-empty band is drawn as a labelled frame that holds exactly the boxes of that band.
% Input: band/2, inside/2 (2_layout.lp) + keep_element/1 + cell/5, cell_label/2, cell_style/3
%        (parsed from 3_view.drawio) + band_rank/2 (asp/common). anc/2 comes from geometry.lp.
% The frame is a vertex with a reserved id; labels and pastel colours are a pipeline convention.
% `other` (Grouping, Location, ...) has no frame: an `other` element that contains elements of band B,
% or is nested in an element of B's frame, belongs to B's frame; any other `other` element stays
% outside every frame (same as frame_rank/2 in asp/gate2/layout.lp).
% Edges are not checked here.

% --- frame table: band, cell id, label, stroke colour, fill colour
band_frame(motivation,  "band-motivation",  "Motivation",  "#a9a9e0", "#f5f5fd").
band_frame(business,    "band-business",    "Business",    "#e6cf6e", "#fffbe8").
band_frame(application, "band-application", "Application", "#86cddb", "#effafc").
band_frame(technology,  "band-technology",  "Technology",  "#9fd096", "#f1f9ef").
frame_cell(F) :- band_frame(_,F,_,_,_).

frame_padding(20).      % between the frame and its boxes
frame_label_space(30).  % above the boxes, for the frame label

% --- which frame an element belongs to
member(E,B) :- keep_element(E), band(E,B), band_rank(B,_).
member(C,B) :- keep_element(C), band(C,other), anc(A,C), band(A,B), band_rank(B,_).
member(C,B) :- keep_element(C), band(C,other), anc(C,P), member(P,B).
used(B) :- member(_,B).

% --- one frame per non-empty band, none for an empty band
violation("BAND-FRAME-MISSING", (F,)) :- used(B), band_frame(B,F,_,_,_), not cell(F,_,_,_,_).
message("BAND-FRAME-MISSING", "The band has elements but no frame vertex (frame id).").

violation("BAND-FRAME-EXTRA", (F,)) :- band_frame(B,F,_,_,_), cell(F,_,_,_,_), not used(B).
message("BAND-FRAME-EXTRA", "Frame vertex of a band that has no element in the view; leave it out.").

% --- label and colours
violation("BAND-FRAME-STYLE", (F,"label",L)) :- band_frame(_,F,L,_,_), cell(F,_,_,_,_), not cell_label(F,L).
violation("BAND-FRAME-STYLE", (F,"strokeColor",S)) :- band_frame(_,F,_,S,_), cell(F,_,_,_,_), not cell_style(F,"strokeColor",S).
violation("BAND-FRAME-STYLE", (F,"fillColor",C)) :- band_frame(_,F,_,_,C), cell(F,_,_,_,_), not cell_style(F,"fillColor",C).
message("BAND-FRAME-STYLE", "The frame's label or colour is not the required one (frame, what, required value).").

% --- the band's boxes lie inside its frame, with room for the label on top and padding around
fits(E,F) :- member(E,B), band_frame(B,F,_,_,_), cell(E,X,Y,W,H), cell(F,FX,FY,FW,FH),
             frame_padding(P), frame_label_space(T),
             X >= FX+P, Y >= FY+T, X+W <= FX+FW-P, Y+H <= FY+FH-P.
violation("BOX-OUTSIDE-FRAME", (E,F)) :- member(E,B), band_frame(B,F,_,_,_), cell(E,_,_,_,_), cell(F,_,_,_,_), not fits(E,F).
message("BOX-OUTSIDE-FRAME", "The box is not completely inside its band's frame, with 30 px for the frame label above and 20 px padding on the other sides (box, frame).").

% --- no box of another band, and no free `other` element, touches the frame
violation("FOREIGN-BOX-IN-FRAME", (E,F)) :- keep_element(E), band_frame(B,F,_,_,_), not member(E,B),
                                            cell(E,X,Y,W,H), cell(F,FX,FY,FW,FH),
                                            X < FX+FW, FX < X+W, Y < FY+FH, FY < Y+H.
message("FOREIGN-BOX-IN-FRAME", "A box that does not belong to this band overlaps its frame (box, frame). Only the band's own boxes may be inside a frame.").

% --- frames are stacked in band order and do not overlap
violation("BAND-FRAME-ORDER", (F1,F2)) :- band_frame(B1,F1,_,_,_), band_frame(B2,F2,_,_,_),
                                          band_rank(B1,R1), band_rank(B2,R2), R1 < R2,
                                          cell(F1,_,Y1,_,H1), cell(F2,_,Y2,_,_), Y1+H1 > Y2.
message("BAND-FRAME-ORDER", "The frame of a higher band must lie completely above the frame of a lower band (higher frame, lower frame).").
