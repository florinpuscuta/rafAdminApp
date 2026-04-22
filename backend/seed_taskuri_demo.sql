-- Seed demo tasks pentru tenant-ul Adpsika (e6cd4519-a2b7-448c-b488-3597a70d3bc3).
-- One-off — nu rulează în migrație. Rulează manual dacă vrei date demo.
DO $$
DECLARE
  tid UUID := 'e6cd4519-a2b7-448c-b488-3597a70d3bc3';
  t1 UUID; t2 UUID; t3 UUID; t4 UUID; t5 UUID; t6 UUID; t7 UUID;
  ag_filip UUID := '4a586159-39cf-49fa-bfe3-4faa6d28e6fb';
  ag_vlad UUID := 'd34a656c-2cb6-4c0d-902f-d828f2ab9d90';
  ag_andrei UUID := 'e0898bc3-ab6f-4914-bce6-403bce6a5800';
  ag_rezso UUID := '550999ce-0987-46a5-b1df-2922eddddb4b';
  ag_adrian UUID := '92b6b88f-806e-4e0d-9975-9f8a4c440fd9';
BEGIN
  t1 := gen_random_uuid();
  INSERT INTO tasks (id, tenant_id, title, description, status, priority, due_date)
  VALUES (t1, tid, 'Verifica stocuri Dedeman Cluj',
    'Confirma cu manager magazin prezenta SKU-urilor prioritare pe raft.',
    'TODO', 'high', CURRENT_DATE + 2);
  INSERT INTO task_assignments (id, task_id, agent_id) VALUES (gen_random_uuid(), t1, ag_filip);

  t2 := gen_random_uuid();
  INSERT INTO tasks (id, tenant_id, title, description, status, priority, due_date)
  VALUES (t2, tid, 'Instalare panou promotional Arabesque Bucuresti',
    'Coordonare cu echipa tehnica + fotografie dupa instalare.',
    'IN_PROGRESS', 'medium', CURRENT_DATE + 5);
  INSERT INTO task_assignments (id, task_id, agent_id) VALUES (gen_random_uuid(), t2, ag_vlad);
  INSERT INTO task_assignments (id, task_id, agent_id) VALUES (gen_random_uuid(), t2, ag_andrei);

  t3 := gen_random_uuid();
  INSERT INTO tasks (id, tenant_id, title, description, status, priority, due_date)
  VALUES (t3, tid, 'Relansare comanda EPS Ambient Ploiesti',
    'Clientul a raportat rupere de stoc - reluat comanda 500mp EPS15.',
    'DONE', 'high', CURRENT_DATE - 3);
  INSERT INTO task_assignments (id, task_id, agent_id) VALUES (gen_random_uuid(), t3, ag_rezso);

  t4 := gen_random_uuid();
  INSERT INTO tasks (id, tenant_id, title, description, status, priority, due_date)
  VALUES (t4, tid, 'Audit facing Brico Timisoara',
    'Poze raft adeziv + mortar; update in app Facing.',
    'TODO', 'low', CURRENT_DATE + 10);
  INSERT INTO task_assignments (id, task_id, agent_id) VALUES (gen_random_uuid(), t4, ag_adrian);

  t5 := gen_random_uuid();
  INSERT INTO tasks (id, tenant_id, title, description, status, priority, due_date)
  VALUES (t5, tid, 'Training nou agent Stefan',
    'Onboarding produse marca privata + proces raportare saptamanala.',
    'IN_PROGRESS', 'medium', CURRENT_DATE + 7);
  INSERT INTO task_assignments (id, task_id, agent_id) VALUES (gen_random_uuid(), t5, ag_filip);

  t6 := gen_random_uuid();
  INSERT INTO tasks (id, tenant_id, title, description, status, priority, due_date)
  VALUES (t6, tid, 'Follow-up oferta mari volume Leroy Pitesti',
    'Trimis email cu oferta; asteptam raspuns pana joi.',
    'TODO', 'high', CURRENT_DATE + 1);
  INSERT INTO task_assignments (id, task_id, agent_id) VALUES (gen_random_uuid(), t6, ag_vlad);

  t7 := gen_random_uuid();
  INSERT INTO tasks (id, tenant_id, title, description, status, priority)
  VALUES (t7, tid, 'Redactare raport lunar martie',
    'Compilare din sales + facing + activitate; trimis la management.',
    'DONE', 'medium');
  INSERT INTO task_assignments (id, task_id, agent_id) VALUES (gen_random_uuid(), t7, ag_andrei);
END $$;
