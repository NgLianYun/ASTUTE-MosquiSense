BEGIN;

DROP TABLE IF EXISTS public.history;
DROP TABLE IF EXISTS public.live_data CASCADE;

CREATE TABLE public.live_data (
    device_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    mosquito_count INTEGER NOT NULL DEFAULT 0 CHECK (mosquito_count >= 0),
    temperature NUMERIC(5,2),
    humidity NUMERIC(5,2),
    battery INTEGER NOT NULL DEFAULT 100 CHECK (battery BETWEEN 0 AND 100),
    fan_status BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO public.live_data
    (device_id, name, location, latitude, longitude, mosquito_count,
     temperature, humidity, battery, fan_status)
VALUES
    ('Q-001', 'Bukit Kerinchi Park',       'Pantai Dalam',       3.09759,101.66145,42,28.70,84.00,88,TRUE),
    ('Q-002', 'Kerinchi Community Path',   'Kampung Kerinchi',    3.10520,101.66510,31,29.10,80.00,91,TRUE),
    ('Q-003', 'Dato Tatah Green Lane',     'Kampung Dato Tatah',  3.10310,101.67320,19,29.30,79.00,85,TRUE),
    ('Q-004', 'Taman Desa Green Walk',     'Taman Desa',          3.10200,101.68500,14,28.50,76.00,90,TRUE),
    ('Q-005', 'Pantai Dalam Trail',        'Pantai Dalam',       3.09120,101.66500, 8,28.80,77.00,95,TRUE),
    ('Q-006', 'Jalan Desa Pedestrian Link','Jalan Desa',         3.09520,101.68220,25,29.40,82.00,79,TRUE),
    ('Q-007', 'Kuala Pauh Riverside Path', 'Kuala Pauh',         3.08740,101.67350,12,28.90,81.00,92,TRUE),
    ('Q-008', 'Salak South Walkway',       'Salak South',        3.08980,101.69100,35,29.20,83.00,86,TRUE);

CREATE TABLE public.history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id TEXT UNIQUE,
    device_id TEXT NOT NULL REFERENCES public.live_data(device_id) ON DELETE CASCADE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    mosquito_count INTEGER NOT NULL CHECK (mosquito_count >= 0),
    temperature NUMERIC(5,2),
    humidity NUMERIC(5,2),
    battery INTEGER CHECK (battery BETWEEN 0 AND 100),
    source TEXT NOT NULL DEFAULT 'simulation'
        CHECK (source IN ('simulation','manual','esp32')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_history_device_time
ON public.history (device_id, recorded_at DESC);


INSERT INTO public.history
    (message_id, device_id, recorded_at, mosquito_count,
     temperature, humidity, battery, source)
SELECT
    'SEED-' || v.device_id || '-' || v.minute_offset,
    v.device_id,
    NOW() - (v.minute_offset * INTERVAL '1 minute'),
    v.mosquito_count,
    d.temperature, d.humidity, d.battery,
    'simulation'
FROM (VALUES
    ('Q-001',10,35),('Q-001',5,39),('Q-001',0,42),
    ('Q-002',10,25),('Q-002',5,28),('Q-002',0,31),
    ('Q-003',10,14),('Q-003',5,16),('Q-003',0,19),
    ('Q-004',10,10),('Q-004',5,12),('Q-004',0,14),
    ('Q-005',10, 5),('Q-005',5, 7),('Q-005',0, 8),
    ('Q-006',10,19),('Q-006',5,22),('Q-006',0,25),
    ('Q-007',10, 8),('Q-007',5,10),('Q-007',0,12),
    ('Q-008',10,28),('Q-008',5,32),('Q-008',0,35)
) AS v(device_id, minute_offset, mosquito_count)
JOIN public.live_data AS d ON d.device_id = v.device_id;


CREATE OR REPLACE FUNCTION public.quito_set_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_live_data_set_timestamp
BEFORE UPDATE ON public.live_data
FOR EACH ROW
EXECUTE FUNCTION public.quito_set_timestamp();


CREATE OR REPLACE FUNCTION public.quito_update_device(
    p_device_id TEXT,
    p_count INTEGER,
    p_temperature NUMERIC,
    p_humidity NUMERIC,
    p_battery INTEGER
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
    IF p_count IS NULL OR p_count < 0 THEN
        RAISE EXCEPTION 'Mosquito count must be zero or greater';
    END IF;

    UPDATE public.live_data
    SET mosquito_count = p_count,
        temperature = p_temperature,
        humidity = p_humidity,
        battery = p_battery
    WHERE device_id = p_device_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Device % not found', p_device_id;
    END IF;

    INSERT INTO public.history
        (message_id, device_id, recorded_at, mosquito_count,
         temperature, humidity, battery, source)
    VALUES
        ('MANUAL-' || pg_catalog.gen_random_uuid()::TEXT,
         p_device_id, NOW(), p_count, p_temperature,
         p_humidity, p_battery, 'manual');
END;
$$;

ALTER TABLE public.live_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Read live device data"
ON public.live_data FOR SELECT TO anon, authenticated USING (TRUE);

CREATE POLICY "Read historical device data"
ON public.history FOR SELECT TO anon, authenticated USING (TRUE);

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT SELECT ON public.live_data, public.history TO anon, authenticated;
REVOKE INSERT, UPDATE, DELETE ON public.live_data, public.history
    FROM anon, authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE
ON public.live_data, public.history TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.history_id_seq TO service_role;

REVOKE ALL ON FUNCTION public.quito_update_device(
    TEXT, INTEGER, NUMERIC, NUMERIC, INTEGER
) FROM PUBLIC, anon, authenticated;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables
            WHERE pubname='supabase_realtime'
              AND schemaname='public' AND tablename='live_data'
        ) THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.live_data;
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables
            WHERE pubname='supabase_realtime'
              AND schemaname='public' AND tablename='history'
        ) THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.history;
        END IF;
    END IF;
END;
$$;

COMMIT;

SELECT device_id, name, location, mosquito_count, updated_at
FROM public.live_data ORDER BY device_id;
SELECT COUNT(*) AS history_records FROM public.history;