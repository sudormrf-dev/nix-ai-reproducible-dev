"""Tests for environment.py."""

from __future__ import annotations

from patterns.environment import (
    AIEnvConfig,
    CudaVersion,
    EnvLayer,
    PythonEnvSpec,
    ReproducibilityReport,
    build_ai_env,
)


class TestCudaVersion:
    def test_none_not_enabled(self):
        assert CudaVersion.NONE.is_enabled() is False

    def test_cuda12_enabled(self):
        assert CudaVersion.CUDA_12.is_enabled() is True

    def test_major_version(self):
        assert CudaVersion.CUDA_12_1.major() == 12

    def test_none_major_zero(self):
        assert CudaVersion.NONE.major() == 0


class TestEnvLayer:
    def test_cuda_optional(self):
        assert EnvLayer.CUDA.is_optional() is True

    def test_base_not_optional(self):
        assert EnvLayer.BASE.is_optional() is False


class TestPythonEnvSpec:
    def test_add_package(self):
        spec = PythonEnvSpec()
        spec.add_package("numpy")
        assert spec.package_count() == 1

    def test_add_package_returns_self(self):
        spec = PythonEnvSpec()
        assert spec.add_package("x") is spec

    def test_has_ml_packages(self):
        spec = PythonEnvSpec(packages=["torch", "requests"])
        assert spec.has_ml_packages() is True

    def test_no_ml_packages(self):
        spec = PythonEnvSpec(packages=["requests", "click"])
        assert spec.has_ml_packages() is False

    def test_to_nix_packages(self):
        spec = PythonEnvSpec(packages=["my-lib"])
        nix = spec.to_nix_packages()
        assert nix[0] == "python3Packages.my_lib"


class TestAIEnvConfig:
    def test_has_cuda(self):
        cfg = AIEnvConfig("test", cuda=CudaVersion.CUDA_12)
        assert cfg.has_cuda() is True

    def test_no_cuda(self):
        cfg = AIEnvConfig("test")
        assert cfg.has_cuda() is False

    def test_add_layer(self):
        cfg = AIEnvConfig("test")
        cfg.add_layer(EnvLayer.CUDA)
        assert EnvLayer.CUDA in cfg.layers

    def test_add_duplicate_layer(self):
        cfg = AIEnvConfig("test")
        cfg.add_layer(EnvLayer.CUDA)
        cfg.add_layer(EnvLayer.CUDA)
        assert cfg.layers.count(EnvLayer.CUDA) == 1

    def test_is_pinned(self):
        cfg = AIEnvConfig("test", pinned_nixpkgs="abc123")
        assert cfg.is_pinned() is True

    def test_not_pinned(self):
        cfg = AIEnvConfig("test")
        assert cfg.is_pinned() is False

    def test_to_dict(self):
        cfg = AIEnvConfig("myenv")
        d = cfg.to_dict()
        assert d["name"] == "myenv"
        assert "layers" in d


class TestReproducibilityReport:
    def test_fully_reproducible(self):
        r = ReproducibilityReport(
            "env", is_pinned=True, has_lock_file=True, hash_verified=True
        )
        assert r.is_reproducible() is True

    def test_impure_not_reproducible(self):
        r = ReproducibilityReport("env", True, True, True, impure_inputs=["curl"])
        assert r.is_reproducible() is False

    def test_score_100(self):
        r = ReproducibilityReport("env", True, True, True)
        assert r.score() == 90

    def test_score_reduced_by_impure(self):
        r = ReproducibilityReport("env", True, True, True, impure_inputs=["x", "y"])
        assert r.score() < 90

    def test_add_warning(self):
        r = ReproducibilityReport("env", False, False, False)
        r.add_warning("missing lock")
        assert len(r.warnings) == 1

    def test_to_dict(self):
        r = ReproducibilityReport("env", True, True, True)
        d = r.to_dict()
        assert d["env"] == "env"


class TestBuildAIEnv:
    def test_with_cuda(self):
        cfg = build_ai_env("ml", ["torch"], CudaVersion.CUDA_12)
        assert cfg.has_cuda()
        assert EnvLayer.CUDA in cfg.layers

    def test_with_ml_packages(self):
        cfg = build_ai_env("ml", ["torch"])
        assert EnvLayer.ML_FRAMEWORK in cfg.layers

    def test_no_ml_no_ml_layer(self):
        cfg = build_ai_env("simple", ["requests"])
        assert EnvLayer.ML_FRAMEWORK not in cfg.layers
