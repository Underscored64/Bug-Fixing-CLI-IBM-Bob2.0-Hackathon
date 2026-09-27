#!/usr/bin/env python3
"""
bugfix.py — Colle un traceback + un fichier de code, obtiens une explication
du bug et un correctif proposé, avec un niveau de confiance.

Usage:
    python3 bugfix.py --code chemin/vers/fichier.py --traceback chemin/vers/erreur.txt
    python3 bugfix.py --code chemin/vers/fichier.py   # traceback collé au prompt

Utilise IBM Bob Shell (CLI `bob`) en mode non-interactif pour l'analyse.
Prérequis : le CLI `bob` installé et accessible dans le PATH, authentifié
(variable d'environnement BOB_API_KEY ou session déjà connectée).
"""

import argparse
import sys
import json
import re
import shutil
import subprocess


PROMPT_TEMPLATE = """Tu es un assistant de debug expert. Voici un traceback/erreur et le code concerné.

=== TRACEBACK ===
{traceback}

=== CODE ===
{code}

Réponds STRICTEMENT en JSON avec ce format, rien d'autre:
{{
  "cause_probable": "explication claire et concise de la cause du bug",
  "corrections": [
    {{"description": "résumé du fix", "code_corrige": "extrait de code corrigé"}}
  ],
  "confiance": "haute|moyenne|faible"
}}
"""


def call_bob(prompt: str) -> dict:
    """
    Appelle IBM Bob Shell en mode non-interactif (bob run --format json) et
    retourne la réponse parsée en dict JSON.
    """
    if shutil.which("bob") is None:
        raise EnvironmentError(
            "Le CLI 'bob' est introuvable dans le PATH. "
            "Vérifie que Bob Shell est installé et accessible depuis ce terminal."
        )

    result = subprocess.run(
        ["bob", "run", "--format", "json", prompt],
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Bob a retourné une erreur (code {result.returncode}):\n{result.stderr}"
        )

    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Sortie inattendue de 'bob run --format json':\n{result.stdout}"
        ) from exc

    if envelope.get("status") != "success":
        raise RuntimeError(f"Session Bob en échec: {envelope}")

    last_message = envelope.get("last_message", "")

    json_match = re.search(r"\{.*\}", last_message, re.DOTALL)
    if not json_match:
        raise ValueError(
            f"Aucun objet JSON trouvé dans la réponse de Bob:\n{last_message}"
        )
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Impossible de parser le JSON retourné par Bob:\n{json_match.group()}"
        ) from exc


def build_prompt(code: str, traceback: str) -> str:
    return PROMPT_TEMPLATE.format(traceback=traceback.strip(), code=code.strip())


def print_result(result: dict):
    print("\n=== CAUSE PROBABLE ===")
    print(result.get("cause_probable", "N/A"))

    print("\n=== CORRECTIFS PROPOSÉS ===")
    for i, fix in enumerate(result.get("corrections", []), 1):
        print(f"\n[{i}] {fix.get('description', '')}")
        print(fix.get("code_corrige", ""))

    print(f"\n=== CONFIANCE: {result.get('confiance', 'N/A').upper()} ===\n")


def main():
    parser = argparse.ArgumentParser(description="Explique un bug et propose un fix via IBM Bob.")
    parser.add_argument("--code", required=True, help="Chemin du fichier de code concerné")
    parser.add_argument("--traceback", help="Chemin du fichier contenant le traceback (sinon saisie interactive)")
    args = parser.parse_args()

    with open(args.code, "r", encoding="utf-8") as f:
        code = f.read()

    if args.traceback:
        with open(args.traceback, "r", encoding="utf-8") as f:
            traceback_text = f.read()
    else:
        print("Colle le traceback puis Ctrl+D (Linux/Mac) ou Ctrl+Z (Windows):")
        traceback_text = sys.stdin.read()

    prompt = build_prompt(code, traceback_text)

    try:
        result = call_bob(prompt)
    except (EnvironmentError, RuntimeError, ValueError) as e:
        print(f"[ERREUR] {e}", file=sys.stderr)
        sys.exit(1)

    print_result(result)


if __name__ == "__main__":
    main()