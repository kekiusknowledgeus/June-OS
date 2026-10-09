"""Operational observability, never fabricated neural internals or hidden reasoning."""
import time
import psutil


class NeuralInspector:
    def __init__(self, runtime):
        self.runtime = runtime

    def supports_internal_inspection(self):
        return False  # A compatible local endpoint also does not expose internals by itself.

    def get_model_info(self):
        c = self.runtime.config
        model = c.gemini_model if c.provider == "gemini" else c.model if c.provider == "openai" else "june_v0_10m" if c.provider == "june_v0" else c.local_model
        return {"provider": c.provider, "model": model, "location": "External" if self.runtime.brain.external else "Local", "model_internals": "unavailable", "supports_internal_inspection": self.supports_internal_inspection()}

    def unavailable(self):
        return {"available": False, "reason": "The configured provider does not expose this data"}

    get_architecture = get_layers = get_parameter_count = get_tensor_shapes = unavailable
    get_tokenization = get_logits = get_token_probabilities = get_attention_data = unavailable
    get_activation_data = get_training_metrics = get_gradient_metrics = unavailable
    get_attention_maps = get_activations = unavailable

    def get_runtime_metrics(self):
        r = self.runtime
        return {"agent_state": r.agent_state, "recent_provider_calls": r.store.list("inference", 20), "working_memory": r.current.snapshot(), "recent_retrieval": r.last_retrieval, "active_tools": r.active_tools, "current_plan": r.current.value("current_plan"), "event_queue": "synchronous dispatch", "pending_events": 0, "jobs": r.store.list("job", 20), "events": r.store.list('event', 12), "recent_tools": r.store.audits(12), "conversation": r.current.value('current_conversation'), "resources": resources(r.config.root)}

def resources(root):
    process = psutil.Process()
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage(str(root))
    processes = []
    for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_times"]):
        try:
            info = p.info
            processes.append({"pid": p.pid, "name": info["name"], "ram_mb": round(info["memory_info"].rss / 1048576, 1), "cpu_seconds_lifetime": round(info["cpu_times"].user + info["cpu_times"].system, 1)})
        except (psutil.Error, AttributeError):
            continue
    return {"observed_at": time.time(), "cpu_percent": psutil.cpu_percent(interval=None), "ram_percent": ram.percent, "ram_available_gb": round(ram.available / 2**30, 2), "disk_free_gb": round(disk.free / 2**30, 1), "june_ram_mb": round(process.memory_info().rss / 2**20, 1), "gpu": {"available": False, "reason": "No GPU telemetry adapter configured"}, "largest_memory_processes": sorted(processes, key=lambda p: p["ram_mb"], reverse=True)[:8], "cpu_measurement": "system utilization since previous sample; per-process values are cumulative CPU time, not current utilization"}
