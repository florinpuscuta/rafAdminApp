-- Seed: mkt_facing + mkt_panouri pentru tenant 'Adpsika'
-- tenant_id = e6cd4519-a2b7-448c-b488-3597a70d3bc3
-- Idempotent: ON CONFLICT DO NOTHING pe constrângerile unice.

DO $$
DECLARE
    t_id UUID := 'e6cd4519-a2b7-448c-b488-3597a70d3bc3';
    b_adeplast UUID;
    b_sika UUID;
    b_ceresit UUID;
    b_mapei UUID;
    b_baumit UUID;
    r_fasade UUID;
    r_interior UUID;
    r_termosistem UUID;
    r_glet UUID;
    r_adezivi UUID;
    r_silicoane UUID;
    st1 UUID;
    st2 UUID;
    st3 UUID;
    y INT := EXTRACT(YEAR FROM NOW())::INT;
    m INT := EXTRACT(MONTH FROM NOW())::INT;
BEGIN
    -- 1. Branduri
    INSERT INTO facing_brands(id, tenant_id, name, color, is_own, display_order, active, created_at)
    VALUES
      (gen_random_uuid(), t_id, 'Adeplast', '#e11d48', true, 1, true, NOW()),
      (gen_random_uuid(), t_id, 'Sika',     '#facc15', true, 2, true, NOW()),
      (gen_random_uuid(), t_id, 'Ceresit',  '#16a34a', false, 10, true, NOW()),
      (gen_random_uuid(), t_id, 'Mapei',    '#0ea5e9', false, 11, true, NOW()),
      (gen_random_uuid(), t_id, 'Baumit',   '#f97316', false, 12, true, NOW())
    ON CONFLICT (tenant_id, name) DO NOTHING;

    SELECT id INTO b_adeplast FROM facing_brands WHERE tenant_id=t_id AND name='Adeplast';
    SELECT id INTO b_sika     FROM facing_brands WHERE tenant_id=t_id AND name='Sika';
    SELECT id INTO b_ceresit  FROM facing_brands WHERE tenant_id=t_id AND name='Ceresit';
    SELECT id INTO b_mapei    FROM facing_brands WHERE tenant_id=t_id AND name='Mapei';
    SELECT id INTO b_baumit   FROM facing_brands WHERE tenant_id=t_id AND name='Baumit';

    -- 2. Raioane parent
    INSERT INTO facing_raioane(id, tenant_id, name, parent_id, display_order, active, created_at)
    VALUES
      (gen_random_uuid(), t_id, 'Fasade',   NULL, 1, true, NOW()),
      (gen_random_uuid(), t_id, 'Interior', NULL, 2, true, NOW())
    ON CONFLICT (tenant_id, name) DO NOTHING;

    SELECT id INTO r_fasade   FROM facing_raioane WHERE tenant_id=t_id AND name='Fasade';
    SELECT id INTO r_interior FROM facing_raioane WHERE tenant_id=t_id AND name='Interior';

    -- 3. Sub-raioane
    INSERT INTO facing_raioane(id, tenant_id, name, parent_id, display_order, active, created_at)
    VALUES
      (gen_random_uuid(), t_id, 'Termosistem', r_fasade,   11, true, NOW()),
      (gen_random_uuid(), t_id, 'Silicoane',   r_fasade,   12, true, NOW()),
      (gen_random_uuid(), t_id, 'Glet',        r_interior, 21, true, NOW()),
      (gen_random_uuid(), t_id, 'Adezivi',     r_interior, 22, true, NOW())
    ON CONFLICT (tenant_id, name) DO NOTHING;

    SELECT id INTO r_termosistem FROM facing_raioane WHERE tenant_id=t_id AND name='Termosistem';
    SELECT id INTO r_glet        FROM facing_raioane WHERE tenant_id=t_id AND name='Glet';
    SELECT id INTO r_adezivi     FROM facing_raioane WHERE tenant_id=t_id AND name='Adezivi';
    SELECT id INTO r_silicoane   FROM facing_raioane WHERE tenant_id=t_id AND name='Silicoane';

    -- 4. 3 stores sample
    SELECT id INTO st1 FROM stores WHERE tenant_id=t_id AND chain='DEDEMAN SRL' LIMIT 1;
    SELECT id INTO st2 FROM stores WHERE tenant_id=t_id AND chain='LEROY MERLIN ROMANIA SRL' LIMIT 1;
    SELECT id INTO st3 FROM stores WHERE tenant_id=t_id AND chain='HORNBACH CENTRALA SRL' LIMIT 1;

    -- 5. Snapshots facings pentru luna curentă (10 rânduri)
    INSERT INTO facing_snapshots(id, tenant_id, year, month, store_id, raion_id, brand_id, facings_count, created_at, updated_at)
    VALUES
      (gen_random_uuid(), t_id, y, m, st1, r_termosistem, b_adeplast, 12, NOW(), NOW()),
      (gen_random_uuid(), t_id, y, m, st1, r_termosistem, b_ceresit,   8, NOW(), NOW()),
      (gen_random_uuid(), t_id, y, m, st1, r_glet,        b_adeplast, 15, NOW(), NOW()),
      (gen_random_uuid(), t_id, y, m, st1, r_glet,        b_mapei,     6, NOW(), NOW()),
      (gen_random_uuid(), t_id, y, m, st2, r_termosistem, b_adeplast,  9, NOW(), NOW()),
      (gen_random_uuid(), t_id, y, m, st2, r_adezivi,     b_sika,      4, NOW(), NOW()),
      (gen_random_uuid(), t_id, y, m, st2, r_adezivi,     b_mapei,     7, NOW(), NOW()),
      (gen_random_uuid(), t_id, y, m, st3, r_silicoane,   b_sika,      5, NOW(), NOW()),
      (gen_random_uuid(), t_id, y, m, st3, r_silicoane,   b_baumit,    3, NOW(), NOW()),
      (gen_random_uuid(), t_id, y, m, st3, r_termosistem, b_baumit,    6, NOW(), NOW())
    ON CONFLICT (tenant_id, year, month, store_id, raion_id, brand_id) DO NOTHING;

    -- 6. Panouri & Standuri (6 exemplare)
    INSERT INTO panou_items(id, tenant_id, store_id, kind, location, installed_at, removed_at, notes, photo_url, created_at, updated_at)
    VALUES
      (gen_random_uuid(), t_id, st1,  'panou', 'Intrare principală',         NOW() - INTERVAL '180 days', NULL,                         'Panou 3x2m brand Adeplast',    NULL, NOW(), NOW()),
      (gen_random_uuid(), t_id, st1,  'stand', 'Raion Fasade, culoar A',     NOW() - INTERVAL '90 days',  NULL,                         'Stand metal 2m — Termosistem', NULL, NOW(), NOW()),
      (gen_random_uuid(), t_id, st2,  'panou', 'Parcare sud',                NOW() - INTERVAL '45 days',  NULL,                         'Panou 4x3m Sika',              NULL, NOW(), NOW()),
      (gen_random_uuid(), t_id, st2,  'stand', 'Raion Adezivi',              NOW() - INTERVAL '300 days', NOW() - INTERVAL '30 days',   'Demontat — reamenajare',       NULL, NOW(), NOW()),
      (gen_random_uuid(), t_id, st3,  'stand', 'Raion Silicoane & Spume',    NOW() - INTERVAL '120 days', NULL,                         'Stand rotativ Sika',           NULL, NOW(), NOW()),
      (gen_random_uuid(), t_id, NULL, 'panou', 'Piața Victoriei, București', NOW() - INTERVAL '365 days', NULL,                         'Panou outdoor independent',    NULL, NOW(), NOW());

    RAISE NOTICE 'Seed complet: brands=% raioane=% snapshots=% panouri=%',
      (SELECT COUNT(*) FROM facing_brands    WHERE tenant_id=t_id),
      (SELECT COUNT(*) FROM facing_raioane   WHERE tenant_id=t_id),
      (SELECT COUNT(*) FROM facing_snapshots WHERE tenant_id=t_id),
      (SELECT COUNT(*) FROM panou_items      WHERE tenant_id=t_id);
END$$;
