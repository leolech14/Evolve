import pytest
import yaml
from pathlib import Path

CONFIG_PATH = Path(".pre-commit-config.yaml")

def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def test_pre_commit_config_valid():
    """Test that the .pre-commit-config.yaml file is valid YAML."""
    try:
        with open(".pre-commit-config.yaml", "r") as f:
            yaml.safe_load(f)
    except Exception as e:
        pytest.fail(f"YAML syntax error: {e}")


def test_repos_key_exists():
    config = load_config()
    assert "repos" in config, "Missing 'repos' key in pre-commit config"
    assert isinstance(config["repos"], list), "'repos' should be a list"


def test_each_repo_has_required_fields():
    config = load_config()
    for i, repo in enumerate(config["repos"]):
        assert "repo" in repo or repo.get("repo", None) == "local", (
            f"Repo #{i} missing 'repo' key"
        )
        if repo.get("repo", None) != "local":
            assert "rev" in repo, f"Repo #{i} missing 'rev' key"
        assert "hooks" in repo, f"Repo #{i} missing 'hooks' key"
        assert isinstance(repo["hooks"], list), f"Repo #{i} 'hooks' should be a list"


def test_each_hook_has_required_fields():
    config = load_config()
    for i, repo in enumerate(config["repos"]):
        for j, hook in enumerate(repo["hooks"]):
            assert "id" in hook, f"Repo #{i} Hook #{j} missing 'id'"
            assert "name" in hook, f"Repo #{i} Hook #{j} missing 'name'"
            assert "description" in hook, f"Repo #{i} Hook #{j} missing 'description'"


def test_no_duplicate_hook_ids_within_repo():
    config = load_config()
    for i, repo in enumerate(config["repos"]):
        ids = [hook["id"] for hook in repo["hooks"] if "id" in hook]
        assert len(ids) == len(set(ids)), f"Duplicate hook ids in repo #{i}: {ids}"


def test_local_repo_hooks_have_entry():
    config = load_config()
    for i, repo in enumerate(config["repos"]):
        if repo.get("repo", None) == "local":
            for j, hook in enumerate(repo["hooks"]):
                assert "entry" in hook, f"Local repo hook #{j} missing 'entry'"
