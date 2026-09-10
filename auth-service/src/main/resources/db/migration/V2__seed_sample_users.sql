-- One sample account per role, so the roles can be seen and tried before
-- real accounts get created through the admin UI. Safe to delete once real
-- accounts exist, nothing else references these rows.
INSERT INTO app_user (username, password_hash, display_name, role) VALUES
    ('viewer1',   '$2b$10$OO89NxBuzUr0xK6W5JbPp.MDVfzU.aN8VFdwulpEoPC4vS6Peklri', 'Sample Viewer',   'VIEWER'),
    ('operator1', '$2b$10$RDdjwLAo80R9.4DyfiDuv.AN/uEcboEPkUnOq2lpBOdlOgLC14NKi', 'Sample Operator', 'OPERATOR'),
    ('admin2',    '$2b$10$LB4vZhvUESzHKs6FbebUq.Mu/X4m0e8.HXHbXPMXwT39SgyamA3rC', 'Sample Admin',    'ADMIN');
