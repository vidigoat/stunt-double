-- A small SaaS company's database, for the one-click "sample Postgres" in the console. Deterministic, no real people.
-- Reachable only inside the compose network; Stunt Double reads it with a read-only role.
CREATE TABLE plans (code text PRIMARY KEY, name text NOT NULL, price numeric(10,2) NOT NULL, seats_included integer NOT NULL);
INSERT INTO plans VALUES ('free', 'Free', 0, 3), ('pro', 'Pro', 49.00, 25), ('business', 'Business', 199.00, 100);

CREATE TABLE accounts (
  account_id uuid PRIMARY KEY, company text NOT NULL, owner_email text NOT NULL, plan text NOT NULL REFERENCES plans(code),
  active boolean NOT NULL, seats integer NOT NULL, mrr numeric(10,2) NOT NULL,
  created_at timestamptz NOT NULL, last_seen_at timestamptz NOT NULL);
INSERT INTO accounts
SELECT md5('acct' || i)::uuid,
       (ARRAY['Northwind','Contoso','Globex','Initech','Umbrella','Hooli','Vandelay','Stark','Wayne','Acme'])[1 + i % 10] || ' ' || i,
       'owner' || i || '@example.com',
       CASE WHEN i % 7 = 0 THEN 'business' WHEN i % 3 = 0 THEN 'pro' ELSE 'free' END,
       i % 11 <> 0, 1 + (i * 37) % 120,
       CASE WHEN i % 7 = 0 THEN 199.00 WHEN i % 3 = 0 THEN 49.00 ELSE 0 END,
       timestamptz '2025-01-01 09:00+00' + (i * interval '17 hours'),
       -- most accounts were seen recently; every 9th has been quiet for months, and some of those still pay
       timestamptz '2026-10-30 12:00+00' - (CASE WHEN i % 9 = 0 THEN 100 + i % 60 ELSE i % 20 END) * interval '1 day'
FROM generate_series(1, 480) AS i;

CREATE TABLE invoices (
  invoice_id bigint PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts(account_id), amount numeric(10,2) NOT NULL,
  status text NOT NULL, issued_on date NOT NULL);
INSERT INTO invoices
SELECT n, a.account_id, a.mrr, CASE WHEN n % 13 = 0 THEN 'unpaid' ELSE 'paid' END, date '2026-10-01' - (m * 30)
FROM (SELECT row_number() OVER () AS n, account_id, mrr, m FROM accounts, generate_series(0, 5) AS m WHERE mrr > 0) AS a;

CREATE ROLE sd_readonly LOGIN PASSWORD 'sd-sample-readonly';
GRANT CONNECT ON DATABASE saas TO sd_readonly;
GRANT USAGE ON SCHEMA public TO sd_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sd_readonly;
