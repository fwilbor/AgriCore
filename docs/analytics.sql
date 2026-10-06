-- AgriCore - the five key business questions in plain SQL.
-- These are what the SQLAlchemy queries in backend/app/routers/analytics.py
-- compile to (simplified). Run them yourself:
--     psql postgresql://agricore:agricore@localhost:5432/agricore -f docs/analytics.sql

\echo '\n== Q1  Low Fuel Alert: active units below 20% fuel =='
SELECT e.serial_number, e.model, e.status, e.fuel_level, f.name AS farm
FROM equipment e
JOIN farms f ON f.id = e.facility_id
WHERE e.status IN ('Idle', 'In-Use')          -- "active" = available or working
  AND e.fuel_level < 20
ORDER BY e.fuel_level;

\echo '\n== Q2  Co-location Discrepancy: units assigned to a farmhand at a different farm =='
SELECT COUNT(*) AS discrepancies
FROM equipment e
JOIN users hand ON hand.id = e.assigned_to_id
WHERE hand.role = 'farm_hand'
  AND hand.farm_id IS DISTINCT FROM e.facility_id;   -- NULL-safe "not equal"

\echo '\n== Q3  Reliability: completion / failure ratio by equipment model =='
SELECT e.model,
       COUNT(*) FILTER (WHERE j.status = 'Completed') AS completed,
       COUNT(*) FILTER (WHERE j.status = 'Failed')    AS failed,
       ROUND(COUNT(*) FILTER (WHERE j.status = 'Completed')::numeric / COUNT(*), 3) AS completion_rate
FROM field_jobs j
JOIN equipment e ON e.id = j.equipment_id
WHERE j.status IN ('Completed', 'Failed')
GROUP BY e.model
ORDER BY completion_rate;

\echo '\n== Q4  Maintenance Flags: farms with more than 30% of (non-retired) equipment in Maintenance =='
SELECT f.name,
       COUNT(e.id)                                         AS total,
       COUNT(e.id) FILTER (WHERE e.status = 'Maintenance') AS in_maintenance,
       ROUND(COUNT(e.id) FILTER (WHERE e.status = 'Maintenance')::numeric
             / NULLIF(COUNT(e.id), 0), 3)                  AS pct
FROM farms f
LEFT JOIN equipment e ON e.facility_id = f.id AND e.status <> 'Retired'
GROUP BY f.id, f.name
HAVING COUNT(e.id) FILTER (WHERE e.status = 'Maintenance')::numeric
       / NULLIF(COUNT(e.id), 0) > 0.30                     -- HAVING filters groups
ORDER BY pct DESC;

\echo '\n== Q5  Reporting Lines: farmhands per supervisor with active (Pending/In-Progress) jobs =='
SELECT sup.full_name AS supervisor,
       COUNT(DISTINCT hand.id)                                   AS direct_reports,
       COUNT(DISTINCT hand.id) FILTER (WHERE j.id IS NOT NULL)   AS with_active_jobs,
       COUNT(DISTINCT j.id)                                      AS active_jobs
FROM users sup
JOIN users hand       ON hand.supervisor_id = sup.id AND hand.role = 'farm_hand' AND hand.is_active
LEFT JOIN field_jobs j ON j.operator_id = hand.id AND j.status IN ('Pending', 'In-Progress')
GROUP BY sup.id, sup.full_name
ORDER BY sup.full_name;
-- For one specific supervisor add:   WHERE sup.full_name = 'Maria Gonzalez'
