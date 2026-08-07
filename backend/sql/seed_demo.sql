USE esp_toolbox;

INSERT INTO devices (device_code, name, location, online_status, firmware_version, last_seen_at, created_at)
VALUES ('FOD-TOOLBOX-001', '一号智能工具箱', '航空维修车间 A 区', 'online', 'p4-demo-0.1.0', NOW(), NOW())
ON DUPLICATE KEY UPDATE online_status = 'online', last_seen_at = NOW();

