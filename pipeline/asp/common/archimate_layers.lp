% ArchiMate 3.x element type -> layout band. From the ArchiMate specification, not from a model.
% Bands: motivation, business, application, technology, other.
% Strategy, implementation & migration and composite elements go to `other` (no ordering).

type_band("Stakeholder", motivation).      type_band("Driver", motivation).
type_band("Assessment", motivation).       type_band("Goal", motivation).
type_band("Outcome", motivation).          type_band("Principle", motivation).
type_band("Requirement", motivation).      type_band("Constraint", motivation).
type_band("Meaning", motivation).          type_band("Value", motivation).

type_band("BusinessActor", business).          type_band("BusinessRole", business).
type_band("BusinessCollaboration", business).  type_band("BusinessInterface", business).
type_band("BusinessProcess", business).        type_band("BusinessFunction", business).
type_band("BusinessInteraction", business).    type_band("BusinessEvent", business).
type_band("BusinessService", business).        type_band("BusinessObject", business).
type_band("Contract", business).               type_band("Representation", business).
type_band("Product", business).

type_band("ApplicationComponent", application).     type_band("ApplicationCollaboration", application).
type_band("ApplicationInterface", application).     type_band("ApplicationFunction", application).
type_band("ApplicationInteraction", application).   type_band("ApplicationProcess", application).
type_band("ApplicationEvent", application).         type_band("ApplicationService", application).
type_band("DataObject", application).

type_band("Node", technology).                    type_band("Device", technology).
type_band("SystemSoftware", technology).          type_band("TechnologyCollaboration", technology).
type_band("TechnologyInterface", technology).     type_band("Path", technology).
type_band("CommunicationNetwork", technology).    type_band("TechnologyFunction", technology).
type_band("TechnologyProcess", technology).       type_band("TechnologyInteraction", technology).
type_band("TechnologyEvent", technology).         type_band("TechnologyService", technology).
type_band("Artifact", technology).                type_band("Equipment", technology).
type_band("Facility", technology).                type_band("DistributionNetwork", technology).
type_band("Material", technology).

type_band("Resource", other).        type_band("Capability", other).
type_band("ValueStream", other).     type_band("CourseOfAction", other).
type_band("WorkPackage", other).     type_band("Deliverable", other).
type_band("ImplementationEvent", other). type_band("Plateau", other).
type_band("Gap", other).             type_band("Grouping", other).
type_band("Location", other).        type_band("Junction", other).

% Top-to-bottom order of the ordered bands. `other` has no rank.
band_rank(motivation,1). band_rank(business,2). band_rank(application,3). band_rank(technology,4).
band_name(B) :- band_rank(B,_).
band_name(other).
