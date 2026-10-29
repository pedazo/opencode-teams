"""Independent OpenCode V2 catalog/selection adapter.

Discovery captures stdout in an anonymous file rather than a pipe to avoid
truncated JSON on affected V2 releases. No credentials are accessed here.
"""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
from urllib.parse import urlencode

MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:/-]*$")
MODEL_REF_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:/-]*)(?:#([A-Za-z0-9][A-Za-z0-9._:-]*))?$")
VARIANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class ConfigError(Exception):
    pass


class Cancelled(Exception):
    pass


def answer(prompt):
    value = input(prompt).strip()
    if value.lower() in ("0", "q", "quit"):
        raise Cancelled()
    return value


def discover_once(args, timeout):
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        raise ConfigError(f"Catalog project is not a directory: {project}")
    executable = args.opencode_bin
    if os.sep in executable:
        executable = str(Path(executable).expanduser().absolute())
    endpoint = "/api/model?" + urlencode({"location[directory]": str(project)})
    with tempfile.TemporaryFile() as capture:
        try:
            process = subprocess.Popen([executable, "api", "get", endpoint], cwd=project,
                                       stdin=subprocess.DEVNULL, stdout=capture,
                                       stderr=subprocess.PIPE, start_new_session=True)
        except OSError as error:
            raise ConfigError(f"Cannot run OpenCode: {error}") from error
        try:
            _, stderr = process.communicate(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise
        if process.returncode:
            raise ConfigError("OpenCode discovery failed: " + stderr.decode(errors="replace")[:4000])
        capture.seek(0)
        raw = capture.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ConfigError("OpenCode catalog exceeds 16 MiB.")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ConfigError("OpenCode returned invalid JSON.") from error
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        raise ConfigError("Invalid OpenCode catalog.")
    if not isinstance(data.get("location"), dict) or data["location"].get("directory") != str(project):
        raise ConfigError("OpenCode catalog belongs to a different project.")
    models = {}
    seen = set()
    for item in data["data"]:
        if not isinstance(item, dict) or not isinstance(item.get("enabled"), bool):
            raise ConfigError("Invalid model catalog entry.")
        if not item["enabled"]:
            continue
        provider, identifier = item.get("providerID"), item.get("id")
        if not isinstance(provider, str) or not isinstance(identifier, str):
            raise ConfigError("Invalid model ID.")
        model = provider + "/" + identifier
        if not MODEL_ID_RE.fullmatch(model):
            raise ConfigError("Invalid model ID.")
        variants = item.get("variants")
        if not isinstance(variants, list) or any(
                not isinstance(v, dict) or not isinstance(v.get("id"), str)
                or not VARIANT_RE.fullmatch(v["id"]) for v in variants):
            raise ConfigError(f"Invalid variants for {model}.")
        choices = tuple(v["id"] for v in variants)
        if model in seen or len(set(choices)) != len(choices):
            raise ConfigError("Duplicate catalog entries.")
        seen.add(model)
        if not args.provider or args.provider == provider:
            models[model] = choices
    return dict(sorted(models.items()))


def discover_models(args):
    deadline = time.monotonic() + 30
    settle = time.monotonic() + 5
    while True:
        try:
            models = discover_once(args, max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as error:
            raise ConfigError("OpenCode model discovery timed out.") from error
        if models:
            return models
        if time.monotonic() >= min(deadline, settle):
            raise ConfigError("No enabled models for this project/provider.")
        time.sleep(0.2)


def choose_provider(models):
    providers = sorted({model.split("/", 1)[0] for model in models})
    if not providers:
        raise ConfigError("No providers have enabled models for this project.")
    print("Providers:")
    for index, provider in enumerate(providers, 1):
        print(f"  {index}. {provider}")
    value = answer("Provider ID or number (0/q/quit cancels): ")
    if value.isdigit() and 1 <= int(value) <= len(providers):
        value = providers[int(value) - 1]
    if value not in providers:
        raise ConfigError(f"No enabled models for provider: {value}")
    return value


def choose_model(args, models):
    if args.model:
        value = args.model
    else:
        for index, model in enumerate(models, 1):
            print(f"  {index}. {model}")
        value = answer("Model ID or number (0/q/quit cancels): ")
        if value.isdigit() and 1 <= int(value) <= len(models):
            value = models[int(value) - 1]
    if value not in models:
        raise ConfigError(f"Not an enabled model: {value}")
    return value


def choose_variant(args, model, known):
    if args.variant is not None:
        if args.variant not in known:
            raise ConfigError(f"Unknown variant for {model}: {args.variant}")
        return args.variant
    if args.interactive and known:
        print("  1. no reasoning variant")
        for index, variant in enumerate(known, 2):
            print(f"  {index}. {variant}")
        value = answer("Reasoning variant ID or number (blank for no variant): ")
        if not value or value == "1":
            return None
        if value.isdigit() and 2 <= int(value) <= len(known) + 1:
            return known[int(value) - 2]
        if value not in known:
            raise ConfigError(f"Unknown variant: {value}")
        return value
    if args.interactive:
        print(f"Reasoning variant: no variant available for {model}.")
    return None


def confirm_interactive():
    value = answer("Apply changes? [y/N]: ").lower()
    if value in ("y", "yes"):
        return True
    if value in ("", "n", "no"):
        return False
    raise ConfigError("Expected yes or no.")
