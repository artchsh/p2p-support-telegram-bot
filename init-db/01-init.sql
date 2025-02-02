-- Create and configure peer2peer database
CREATE DATABASE peer2peer;
\c peer2peer;

CREATE USER octoberskyler WITH PASSWORD 'kimep';
ALTER USER octoberskyler WITH SUPERUSER;
GRANT ALL PRIVILEGES ON DATABASE peer2peer TO octoberskyler;
GRANT ALL ON SCHEMA public TO octoberskyler;
GRANT ALL ON ALL TABLES IN SCHEMA public TO octoberskyler;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO octoberskyler;
