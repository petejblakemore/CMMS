PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE locations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    parent_id       INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    description     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    active          INTEGER NOT NULL DEFAULT 1
);
INSERT INTO locations VALUES(1,'Plas Gwernoer',NULL,'Main house','2026-06-07 14:30:58',1);
INSERT INTO locations VALUES(2,'Gwernoer Bach',NULL,'Cottage','2026-06-07 14:30:58',1);
INSERT INTO locations VALUES(3,'Workshop',NULL,'Main workshop','2026-06-07 14:30:58',1);
INSERT INTO locations VALUES(4,'Barn',NULL,'Barn and outbuildings','2026-06-07 14:30:58',1);
INSERT INTO locations VALUES(5,'Vehicles',NULL,'Vehicle fleet','2026-06-07 14:30:58',1);
INSERT INTO locations VALUES(6,'Farm',NULL,'Fields, fences, water, etc.','2026-06-07 14:30:58',1);
INSERT INTO locations VALUES(8,'Main Hallway',11,'Main hallway on ground floor','2026-06-07 15:01:21',1);
INSERT INTO locations VALUES(9,'Main Office',11,'Ann''s office','2026-06-07 15:01:56',1);
INSERT INTO locations VALUES(10,'Kitchen',10,'Kitchen','2026-06-07 15:02:22',1);
INSERT INTO locations VALUES(11,'Plas Gwernoer Ground Floor',1,'Ground Floor Plas Gwernoer','2026-06-07 15:02:53',1);
INSERT INTO locations VALUES(12,'Utility Room',11,'Utility room','2026-06-07 17:56:19',1);
INSERT INTO locations VALUES(13,'Bedroom 1',11,'Bedroom 1 (Maria & Judy''s room)','2026-06-07 17:57:17',1);
INSERT INTO locations VALUES(14,'Dining Room',11,'Small extension on kitchen','2026-06-07 17:57:55',1);
INSERT INTO locations VALUES(15,'Bedroom 2',11,'Bedroom 2 Workshop','2026-06-07 17:59:52',1);
INSERT INTO locations VALUES(16,'Gun Cupboard',11,'Gun and Comms cupboard','2026-06-07 18:00:50',1);
INSERT INTO locations VALUES(17,'Front Room',11,NULL,'2026-06-07 18:01:19',1);
INSERT INTO locations VALUES(18,'Plas Gwernoer First Floor',1,'First Floor','2026-06-07 18:02:24',1);
INSERT INTO locations VALUES(19,'Bathroom',18,'Bathroom','2026-06-07 18:02:49',1);
INSERT INTO locations VALUES(20,'Master Bedroom',18,'Master Bedroom','2026-06-07 18:03:16',1);
INSERT INTO locations VALUES(21,'Small Bedroom',18,'Small Bedroom (Upstairs)','2026-06-07 18:03:45',1);
INSERT INTO locations VALUES(22,'Roof Space Rear',18,'Roof Space Rear','2026-06-07 18:04:24',1);
INSERT INTO locations VALUES(23,'Roof Space Front',18,'Roof Space Front','2026-06-07 18:05:43',1);
INSERT INTO locations VALUES(24,'Upstairs Hallway',18,'Upstairs Hallway ','2026-06-07 18:07:41',1);
INSERT INTO locations VALUES(25,'Gwernoer Bach Front Room',2,'Front Room','2026-06-07 18:09:17',1);
INSERT INTO locations VALUES(26,'Gwernoer Bach Bathroom',2,'Gwernoer Bach Bathroom','2026-06-07 18:48:29',1);
INSERT INTO locations VALUES(27,'Gwernoer Bach Bedroom 1',2,'Gwernoer Bach Bedroom 1 on right with back to front door','2026-06-07 18:49:28',1);
INSERT INTO locations VALUES(28,'Gwernoer Bach Bedroom 2',2,'Gwernoer Bach Bedroom 2 on left with back to front door','2026-06-07 18:49:57',1);
INSERT INTO locations VALUES(29,'Gwernoer Bach Garage',2,'Gwernoer Bach Garage','2026-06-07 18:50:44',1);
INSERT INTO locations VALUES(30,'Gwernoer Bach Kitchen',2,'Gwernoer Bach Kitchen','2026-06-07 18:51:31',1);
INSERT INTO locations VALUES(31,'Gwernoer Bach Rear paved area',2,'Gwernoer Bach Rear paved area','2026-06-07 18:52:01',1);
INSERT INTO locations VALUES(32,'Gwernoer Bach Front Covered Area',2,'Gwernoer Bach Front Covered Area','2026-06-07 18:52:52',1);
INSERT INTO locations VALUES(33,'LD15AHL Citroen Relay Van',5,'LD15AHL Citroen Relay Van','2026-06-07 18:54:51',0);
INSERT INTO locations VALUES(34,'FP72DGE Toyota C-CHR',5,'FP72DGE Toyota C-CHR','2026-06-07 18:55:31',0);
INSERT INTO locations VALUES(35,'LL10SFU Kia Sorento',5,'LL10SFU Kia Sorento','2026-06-07 18:58:45',0);
INSERT INTO locations VALUES(36,'Kubota Tractor',5,NULL,'2026-06-15 19:44:01',0);
CREATE TABLE assets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    location_id         INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    category            TEXT,          -- e.g. Heating, Plumbing, Vehicle, Structure
    type                TEXT,          -- freeform subtype if needed
    manufacturer        TEXT,
    model               TEXT,
    serial_number       TEXT,
    purchase_date       TEXT,          -- ISO date
    warranty_end_date   TEXT,          -- ISO date
    status              TEXT NOT NULL DEFAULT 'Running', -- Running / Needs Maintenance / Out of Service
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
, cost REAL, vendor TEXT);
INSERT INTO assets VALUES(1,'Rayburn',1,'Heating','Boiler','Rayburn','Royal',NULL,NULL,NULL,'Running','Solid fuel Rayburn supplying hot water and some radiators','2026-06-07 14:30:58',NULL,NULL);
INSERT INTO assets VALUES(2,'Smeg Cooker',1,'Appliance','Cooker','Smeg','Range',NULL,NULL,NULL,'Running','Main kitchen cooker','2026-06-07 14:30:58',NULL,NULL);
INSERT INTO assets VALUES(3,'Waste Water system',6,'Infrastructure','Waste water',NULL,NULL,NULL,NULL,NULL,'Running','Septic tank and associated pipework','2026-06-07 14:30:58',NULL,NULL);
INSERT INTO assets VALUES(4,'BMW R1100RT',5,'Vehicle','Motorcycle','BMW','R1100RT',NULL,NULL,NULL,'Running','Touring bike','2026-06-07 14:30:58',NULL,NULL);
INSERT INTO assets VALUES(5,'Citroen Relay van',5,'Vehicle','Van','Citroen','Relay',NULL,NULL,NULL,'Running','Van used for general hauling and (future) camper conversion','2026-06-07 14:30:58',NULL,NULL);
INSERT INTO assets VALUES(6,'Toyota C-HR',5,'Vehicle','Car','Toyota','C-HR',NULL,NULL,NULL,'Running',NULL,'2026-06-07 17:51:38',NULL,NULL);
INSERT INTO assets VALUES(7,'Honda Mower',3,'Grounds','Mower','Honda',NULL,NULL,'2026-06-18',NULL,'Running',NULL,'2026-06-07 17:55:35',NULL,NULL);
INSERT INTO assets VALUES(8,'Honeywell Evohome Thermostatic valve',9,'Heating','Thermostatic Valve','Honeywell',' HR92 Multi-Zone Head',NULL,NULL,NULL,'Running',NULL,'2026-06-11 20:20:02',NULL,NULL);
INSERT INTO assets VALUES(9,'Honeywell Evohome Thermostatic valve',8,'Heating','Thermostatic Valve','Honeywell','HR92 Multi-Zone Head',NULL,NULL,NULL,'Running',NULL,'2026-06-11 20:24:29',NULL,NULL);
INSERT INTO assets VALUES(10,'Honeywell Evohome Thermostatic Valve',19,'Heating','Thermostatic Valve','Honeywell','HR92 Multi-Zone Head',NULL,NULL,NULL,'Running',NULL,'2026-06-11 20:26:16',NULL,NULL);
INSERT INTO assets VALUES(12,'Honeywell Evohome Thermostatic valve',15,'Heating',NULL,'Honeywell','HR92 Multi-Zone Head',NULL,NULL,NULL,'Running',NULL,'2026-06-15 19:28:50',NULL,NULL);
INSERT INTO assets VALUES(14,'MIG Welder',3,'Tools',NULL,NULL,NULL,NULL,NULL,NULL,'Running',NULL,'2026-06-16 10:07:17',NULL,NULL);
INSERT INTO assets VALUES(16,'Stand Mixer',10,'Appliance','Kitchen','Kitchen Aid','MIXER TILT-HEAD 4.7L ',NULL,NULL,NULL,'Running',NULL,'2026-06-18 17:42:30',NULL,NULL);
INSERT INTO assets VALUES(18,'Smoke Alarm',25,'Smoke Alarm','Alarm',NULL,NULL,NULL,NULL,NULL,'Running',NULL,'2026-06-19 18:56:11',NULL,NULL);
INSERT INTO assets VALUES(19,'Lenovo Thinkpad P52s',1,'IT','Computer','Lenovo','Lenovo Thinkpad P52s',NULL,'2019-09-28','2021-09-28','Running',replace(replace('Lenovo ThinkPad P52s 15.6-inch Laptop - (Intel Core i7-8550u Processor, 15.6" Full HD IPS Screen,16GB DDR4 RAM, 256 GB SSD, Nvidia Quadro P500 Graphics, Windows 10 Professional)\r\nSold by: Box Online Technology Store\r\n£999.97','\r',char(13)),'\n',char(10)),'2026-06-19 21:08:54',NULL,NULL);
INSERT INTO assets VALUES(20,'Apple Mac mini Desktop Computer with M4 chip',1,'IT','Computer','Apple','Apple Mac mini  M4 chip','RC751FRQPN','2025-02-03',NULL,'Running','Apple Mac mini Desktop Computer with M4 chip with 10 core CPU and 10 core GPU: Built for Apple Intelligence, 16GB Unified Memory, 512GB SSD Storage, Gigabit Ethernet. Works with iPhone/iPad','2026-06-19 21:11:32',568.98999999999997356,'Amazon');
INSERT INTO assets VALUES(21,'Kia Sorento',5,'Vehicle','Car','Kia','Sorento',NULL,NULL,NULL,'Running',NULL,'2026-06-20 07:23:28',NULL,NULL);
INSERT INTO assets VALUES(22,'Withings Smart Body Analyser',19,'IT','Device','Withings','Withings Smart Body Analyser','00:24:e4:37:3f:02','2016-01-11',NULL,'Running',NULL,'2026-06-20 13:51:25',NULL,NULL);
INSERT INTO assets VALUES(23,'Kindle Paperwhite',20,'IT','Device','Amazon','Kindle Paperwhite (10th Generation)','G000T21393270AKX',NULL,NULL,'Running',replace(replace('Pete''s Kindle\r\nEdit\r\nEmail :\r\npete_EunDzd@kindle.com\r\nEdit\r\nType :\r\nKindle Paperwhite (10th Generation)\r\nSerial number :\r\nG000T21393270AKX\r\nDevice registered on :\r\n8 August 2022\r\nSoftware security updates :\r\nNo longer guaranteed.Learn more\r\nKindle Paperwhite (4th edition)	(KPW) Older Paperwhite and Kindle e-reader Models	2018','\r',char(13)),'\n',char(10)),'2026-06-20 19:48:09',NULL,NULL);
INSERT INTO assets VALUES(24,'Hall Safe',16,'Security','Safe','Brattonsound',NULL,NULL,NULL,NULL,'Running',NULL,'2026-06-24 17:15:38',NULL,NULL);
INSERT INTO assets VALUES(25,'Electricity Meter',12,'Meter','Electricity',NULL,NULL,NULL,NULL,NULL,'Running',NULL,'2026-06-25 12:35:36',NULL,NULL);
INSERT INTO assets VALUES(26,'Gas Meter',1,'Meter','Gas',NULL,NULL,NULL,NULL,NULL,'Running',NULL,'2026-06-25 12:37:57',NULL,NULL);
INSERT INTO assets VALUES(27,'Synology DS920+ 4 Bay NAS Enclosure',8,'IT','Computer','Synology','DS920+','2260TER10SJQY','2023-01-24',NULL,'Running',NULL,'2026-06-25 14:35:54',NULL,NULL);
INSERT INTO assets VALUES(28,'Google Nest Protect Battery Smoke & CO Alarm',8,'Smoke Alarm','Alarm','Google','Topaz 2.9','06AA01AC522006P1',NULL,NULL,'Running',NULL,'2026-06-25 14:37:44',NULL,NULL);
INSERT INTO assets VALUES(29,'Wall Safe',22,'Security','Safe',NULL,NULL,NULL,NULL,NULL,'Running',NULL,'2026-06-25 15:55:13',NULL,NULL);
INSERT INTO assets VALUES(32,'Intergas 24kw Boiler with flue',22,'Appliance','Boiler','Intergas','Intergas 24kw ',NULL,NULL,NULL,'Running',NULL,'2026-06-25 16:41:45',NULL,'GasSafe4U');
CREATE TABLE maintenance_plans (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id            INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    description         TEXT,
    frequency_unit      TEXT NOT NULL,    -- day / month / year
    frequency_value     INTEGER NOT NULL, -- every N units
    last_done_date      TEXT,            -- ISO date
    next_due_date       TEXT,            -- ISO date, can be precomputed
    active              INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
, location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL);
INSERT INTO maintenance_plans VALUES(1,1,'Sweep Chimney','Annual sweep of Rayburn flue and chimney','year',1,NULL,'2026-09-07',1,'2026-06-07 14:30:58',NULL);
INSERT INTO maintenance_plans VALUES(2,25,'Read Electricity Meter','Read meter and submit to energy provider','month',1,NULL,'2026-07-23',1,'2026-06-25 12:36:44',NULL);
INSERT INTO maintenance_plans VALUES(3,26,'Read Meter','Read meter and submiy to provider','month',1,NULL,'2026-07-23',1,'2026-06-25 12:38:38',NULL);
CREATE TABLE work_orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id            INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    location_id         INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    title               TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'Open',  -- Open / In Progress / Done / Cancelled
    priority            TEXT NOT NULL DEFAULT 'Normal', -- Low / Normal / High / Urgent
    source              TEXT,           -- Manual, Auto from PM, Inspection, etc.
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    due_date            TEXT,           -- ISO date
    completed_at        TEXT,
    closed_notes        TEXT
);
INSERT INTO work_orders VALUES(1,3,6,'DO some work','Workorder to test','Done','Normal','Manual','2026-06-07 16:23:07','2026-06-17','2026-06-07 16:25:50',NULL);
INSERT INTO work_orders VALUES(4,NULL,31,'Repair gap in wall','Back of holiday let has a gap where we suspect rats are using as an access','Open','Low','Manual','2026-06-11 19:35:53',NULL,NULL,NULL);
INSERT INTO work_orders VALUES(11,21,5,'Replace rear lock','Rear lock on passenger side','Open','Low','Manual','2026-06-20 07:24:17',NULL,NULL,NULL);
INSERT INTO work_orders VALUES(13,23,3,'Replace battery','Replace battery on Kindle','Done','Normal','Manual','2026-06-20 20:30:13','2026-06-25','2026-06-24 12:30:55','Battery sourced and replaced, need to charge to 100% then completely discharge for calibration');
INSERT INTO work_orders VALUES(14,NULL,1,'Repair Garden fence','Replace rotted uprights and repair / replace panels','Open','Normal','Manual','2026-06-21 08:38:21',NULL,NULL,NULL);
INSERT INTO work_orders VALUES(15,NULL,31,'Repoint steps from house to holiday let','Repoint steps from house to holiday let','Open','Low','Manual','2026-06-21 08:40:04',NULL,NULL,NULL);
INSERT INTO work_orders VALUES(16,5,NULL,'Install dedicated charger','Install dedicated charger to keep main van battery topped up','Queued','Low','Manual','2026-06-21 10:46:26',NULL,'2026-06-24 10:12:10',NULL);
CREATE TABLE work_order_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id   INTEGER NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    event_time      TEXT NOT NULL DEFAULT (datetime('now')),
    old_status      TEXT,
    new_status      TEXT,
    note            TEXT
);
INSERT INTO work_order_history VALUES(1,1,'2026-06-07 16:25:38','Open','In Progress',NULL);
INSERT INTO work_order_history VALUES(2,1,'2026-06-07 16:25:50','In Progress','Done',NULL);
INSERT INTO work_order_history VALUES(12,8,'2026-06-15 13:51:06','Open','Open',NULL);
INSERT INTO work_order_history VALUES(14,7,'2026-06-15 14:08:59','Queued','Open',NULL);
INSERT INTO work_order_history VALUES(16,4,'2026-06-18 15:50:45','Queued','Open','status change test');
INSERT INTO work_order_history VALUES(18,16,'2026-06-24 10:12:10','Open','Done',NULL);
INSERT INTO work_order_history VALUES(19,16,'2026-06-24 10:12:27','Done','Queued','Edited via edit form');
INSERT INTO work_order_history VALUES(20,13,'2026-06-24 12:30:55','Open','Done','kindle on charge');
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO users VALUES(1,'pete','$2b$12$9VZzdKlZcEtjes.I47DnSOZDEmdZ7Xk9XgvaUIi1ewAx2Dzzu.gUi','Pete','2026-06-18 11:38:23');
CREATE TABLE job_plan_steps (id INTEGER PRIMARY KEY AUTOINCREMENT, maintenance_plan_id INTEGER NOT NULL REFERENCES maintenance_plans(id) ON DELETE CASCADE, step_number INTEGER NOT NULL, description TEXT NOT NULL, notes TEXT);
DELETE FROM sqlite_sequence;
INSERT INTO sqlite_sequence VALUES('locations',38);
INSERT INTO sqlite_sequence VALUES('assets',32);
INSERT INTO sqlite_sequence VALUES('maintenance_plans',3);
INSERT INTO sqlite_sequence VALUES('work_orders',16);
INSERT INTO sqlite_sequence VALUES('work_order_history',20);
INSERT INTO sqlite_sequence VALUES('users',2);
CREATE INDEX idx_assets_location ON assets(location_id);
CREATE INDEX idx_assets_status   ON assets(status);
CREATE INDEX idx_maintenance_asset   ON maintenance_plans(asset_id);
CREATE INDEX idx_maintenance_nextdue ON maintenance_plans(next_due_date);
CREATE INDEX idx_work_orders_status   ON work_orders(status);
CREATE INDEX idx_work_orders_duedate  ON work_orders(due_date);
CREATE INDEX idx_work_orders_location ON work_orders(location_id);
CREATE INDEX idx_wo_history_wo ON work_order_history(work_order_id);
CREATE VIEW v_upcoming_pm AS
SELECT
    mp.id             AS plan_id,
    mp.title,
    mp.description,
    mp.next_due_date,
    a.id              AS asset_id,
    a.name            AS asset_name,
    l.id              AS location_id,
    l.name            AS location_name
FROM maintenance_plans mp
JOIN assets a ON a.id = mp.asset_id
JOIN locations l ON l.id = a.location_id
WHERE mp.active = 1
  AND mp.next_due_date IS NOT NULL;
CREATE VIEW v_open_work_orders AS
SELECT
    w.id              AS work_order_id,
    w.title,
    w.status,
    w.priority,
    w.due_date,
    w.created_at,
    a.id              AS asset_id,
    a.name            AS asset_name,
    l.id              AS location_id,
    l.name            AS location_name
FROM work_orders w
LEFT JOIN assets a   ON a.id = w.asset_id
LEFT JOIN locations l ON l.id = COALESCE(w.location_id, a.location_id)
WHERE w.status IN ('Open','In Progress');
CREATE VIEW v_queued_work_orders AS
SELECT
    w.id              AS work_order_id,
    w.title,
    w.status,
    w.priority,
    w.due_date,
    w.created_at,
    a.id              AS asset_id,
    a.name            AS asset_name,
    l.id              AS location_id,
    l.name            AS location_name
FROM work_orders w
LEFT JOIN assets a    ON a.id = w.asset_id
LEFT JOIN locations l ON l.id = COALESCE(w.location_id, a.location_id)
WHERE w.status = 'Queued';
CREATE INDEX idx_job_steps_plan ON job_plan_steps(maintenance_plan_id);
CREATE VIEW v_assets AS SELECT a.id AS asset_id, a.name AS asset_name, a.category, a.type, a.status, l.id AS location_id, l.name AS location_name, a.manufacturer, a.model, a.serial_number, a.purchase_date, a.warranty_end_date, a.cost, a.vendor FROM assets a JOIN locations l ON l.id = a.location_id;
COMMIT;
