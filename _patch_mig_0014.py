path = r"hechos\migrations\0014_escuela_anio_ciclo_grupo.py"
old = """        migrations.AlterUniqueTogether(
            name="escuela",
            unique_together={("sede", "nombre", "anio", "ciclo", "grupo")},
        ),
    ]
"""
new = """        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterUniqueTogether(
                    name="escuela",
                    unique_together={("sede", "nombre", "anio", "ciclo", "grupo")},
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql=r'''
                    DO $$ BEGIN
                        ALTER TABLE hechos_escuela
                        ADD CONSTRAINT hechos_escuela_sede_nombre_anio_ciclo_grupo_uniq
                            UNIQUE (sede_id, nombre, anio, ciclo, grupo);
                    EXCEPTION
                        WHEN duplicate_object THEN NULL;
                    END $$;
                    ''',
                    reverse_sql='''
                    ALTER TABLE hechos_escuela
                    DROP CONSTRAINT IF EXISTS hechos_escuela_sede_nombre_anio_ciclo_grupo_uniq;
                    ''',
                ),
            ],
        ),
    ]
"""
from pathlib import Path
base = Path(__file__).resolve().parent
text = (base / path).read_text(encoding="utf-8")
if old not in text:
    raise SystemExit("pattern not found")
(base / path).write_text(text.replace(old, new), encoding="utf-8")
print("patched")
