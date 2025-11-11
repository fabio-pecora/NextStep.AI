import psycopg

dsn = "postgresql://postgres.zbqzfmjdcfagobdyrvva:fabbofabbO1..@aws-1-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require"

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("select 1;")
        print(cur.fetchone())
