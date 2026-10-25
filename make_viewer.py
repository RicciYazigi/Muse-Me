"""Static, read-only P0 viewer. Observed content is always rendered as escaped text."""
from html import escape
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def render(data):
    def esc(value):
        return escape(str(value), quote=True)
    package = data["package"]
    apps = sorted({event["application"] for event in data["activity"]})
    apps_html = "".join(f"<li>{esc(app)}</li>" for app in apps)
    activity = []
    for event in data["activity"]:
        content = "Contenido restringido: oculto" if event["permission_scope"] == "restricted" else event["content"]
        activity.append(f"<article><small>{esc(event['ts'])} · {esc(event['kind'])}</small>"
                        f"<b>{esc(event['application'])}</b><p>{esc(content)}</p>"
                        f"<small>{esc(event['epistemic_status'])} · {esc(event['permission_scope'])}</small></article>")
    selected = "".join(f"<article class='selected'><b>{esc(item['app'])}</b><p>{esc(item['content'])}</p>"
                       f"<small>{esc(item['status'])} · {esc(item['source'])}</small></article>"
                       for item in package["additional_context"])
    excluded = "".join(f"<li>{esc(item['app'])}: {esc(item['reason'])}</li>" for item in package["excluded_context"])
    chain = "".join(f"<li>{esc(link['kind'])} <code>{esc(link['hash'][:16])}…</code></li>" for link in data["chain"])
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Muse Environment · P0 local</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#10151c;color:#e8eef4;font:15px system-ui}}
header,main,footer{{max-width:1440px;margin:auto;padding:24px}}header{{border-bottom:1px solid #354150}}
h1{{margin:0 0 8px;font-size:26px}}h2{{font-size:18px}}p{{line-height:1.5;overflow-wrap:anywhere}}
.badge{{color:#f4c67b}}.grid{{display:grid;grid-template-columns:.7fr 1.2fr 1.2fr;gap:18px}}
section,.result{{background:#17202b;border:1px solid #354150;border-radius:12px;padding:18px;min-width:0}}
article{{border-top:1px solid #354150;padding:14px 0}}article b{{display:block;margin-top:6px}}
small,footer{{color:#afbfce}}small,code{{overflow-wrap:anywhere}}.selected{{border-left:3px solid #69cda4;padding-left:12px}}
li{{margin:10px 0}}details{{margin-top:20px}}summary{{cursor:pointer}}.result{{margin-top:18px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;line-height:1.6}}
@media(max-width:950px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>Muse Environment</h1>
<p class="badge">P0 simulado · visor de una ejecución · proveedor local · llamadas Meta: {esc(data['meta_calls'])}</p>
<p>Aplicaciones → actividad → memoria contextual → borrador revisado → inserción.</p></header>
<main><div class="grid"><section><h2>Aplicaciones</h2><ul>{apps_html}</ul>
<p>Captura real de Windows: pendiente.<br>Este visor no observa tu escritorio.</p>
<p>Memoria recuperada al reabrir: <b>{esc(data['persistence']['reopened_ok'])}</b></p>
<p>Eventos guardados: {esc(data['persistence']['after'])}</p></section>
<section><h2>Flujo de actividad</h2>{''.join(activity)}</section>
<section><h2>Contexto seleccionado</h2><p>{esc(package['current_context']['content'])}</p>{selected}
<details><summary>Exclusiones locales</summary><ul>{excluded}</ul></details></section></div>
<section class="result"><h2>Borrador e intervención</h2><pre>{esc(data['invoke']['draft']['text'])}</pre>
<p>Estado: <b>{esc(data['invoke']['status'])}</b>. Aprobación y superficie simuladas; no se envió un mensaje.</p>
<p>Ensayo Fuse preparado: índice {esc(data['ab']['fuse_stop'])}; intento de inserción {esc(data['ab']['attempt_status'])};
inserciones tras STOP: {esc(data['ab']['blocked_insertions'])}. No demuestra eficacia estadística.</p>
<details><summary>Registro de intervenciones · integridad: {esc(data['chain_valid'])}</summary><ul>{chain}</ul></details>
</section></main><footer>Fuentes y relaciones conservan su procedencia. El hash comprueba el contenido registrado; no certifica su verdad.</footer></body></html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    data = json.loads((args.output_dir / "resultado_demo.json").read_text(encoding="utf-8"))
    path = args.output_dir / "viewer.html"
    path.write_text(render(data), encoding="utf-8")
    print("viewer ok:", path)


if __name__ == "__main__":
    main()
