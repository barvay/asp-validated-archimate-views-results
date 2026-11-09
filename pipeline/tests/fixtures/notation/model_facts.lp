% Test model for asp/gate3/notation.lp: one relation per notation kind, each between its own two elements.

element("r_comp_s", "ApplicationComponent", "r_comp source").
element("r_comp_t", "ApplicationComponent", "r_comp target").
element("r_aggr_s", "ApplicationComponent", "r_aggr source").
element("r_aggr_t", "ApplicationComponent", "r_aggr target").
element("r_assign_s", "ApplicationComponent", "r_assign source").
element("r_assign_t", "ApplicationComponent", "r_assign target").
element("r_real_s", "ApplicationComponent", "r_real source").
element("r_real_t", "ApplicationComponent", "r_real target").
element("r_serv_s", "ApplicationComponent", "r_serv source").
element("r_serv_t", "ApplicationComponent", "r_serv target").
element("r_trig_s", "ApplicationComponent", "r_trig source").
element("r_trig_t", "ApplicationComponent", "r_trig target").
element("r_flow_s", "ApplicationComponent", "r_flow source").
element("r_flow_t", "ApplicationComponent", "r_flow target").
element("r_infl_s", "ApplicationComponent", "r_infl source").
element("r_infl_t", "ApplicationComponent", "r_infl target").
element("r_spec_s", "ApplicationComponent", "r_spec source").
element("r_spec_t", "ApplicationComponent", "r_spec target").
element("r_acc_w_s", "ApplicationComponent", "r_acc_w source").
element("r_acc_w_t", "ApplicationComponent", "r_acc_w target").
element("r_acc_r_s", "ApplicationComponent", "r_acc_r source").
element("r_acc_r_t", "ApplicationComponent", "r_acc_r target").
element("r_acc_a_s", "ApplicationComponent", "r_acc_a source").
element("r_acc_a_t", "ApplicationComponent", "r_acc_a target").
element("r_acc_rw_s", "ApplicationComponent", "r_acc_rw source").
element("r_acc_rw_t", "ApplicationComponent", "r_acc_rw target").
element("r_assoc_d_s", "ApplicationComponent", "r_assoc_d source").
element("r_assoc_d_t", "ApplicationComponent", "r_assoc_d target").
element("r_assoc_u_s", "ApplicationComponent", "r_assoc_u source").
element("r_assoc_u_t", "ApplicationComponent", "r_assoc_u target").

relation("r_comp", "Composition", "r_comp_s", "r_comp_t").
relation("r_aggr", "Aggregation", "r_aggr_s", "r_aggr_t").
relation("r_assign", "Assignment", "r_assign_s", "r_assign_t").
relation("r_real", "Realization", "r_real_s", "r_real_t").
relation("r_serv", "Serving", "r_serv_s", "r_serv_t").
relation("r_trig", "Triggering", "r_trig_s", "r_trig_t").
relation("r_flow", "Flow", "r_flow_s", "r_flow_t").
relation("r_infl", "Influence", "r_infl_s", "r_infl_t").
relation("r_spec", "Specialization", "r_spec_s", "r_spec_t").
relation("r_acc_w", "Access", "r_acc_w_s", "r_acc_w_t").
relation("r_acc_r", "Access", "r_acc_r_s", "r_acc_r_t").
relation("r_acc_a", "Access", "r_acc_a_s", "r_acc_a_t").
relation("r_acc_rw", "Access", "r_acc_rw_s", "r_acc_rw_t").
relation("r_assoc_d", "Association", "r_assoc_d_s", "r_assoc_d_t").
relation("r_assoc_u", "Association", "r_assoc_u_s", "r_assoc_u_t").

access_type("r_acc_w", "write").
access_type("r_acc_r", "read").
access_type("r_acc_a", "access").
access_type("r_acc_rw", "readwrite").
directed("r_assoc_d").
