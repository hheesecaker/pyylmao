from __future__ import annotations


LLM_RELOAD_MODULES = [
    "llama_index.core.base.llms",
    "llama_index.core.base.llms.base",
    "llama_index.core.base.llms.generic_utils",
    "llama_index.core.base.llms.types",
    "llama_index.core.callbacks.simple_llm_handler",
    "llama_index.core.indices.property_graph.sub_retrievers.llm_synonym",
    "llama_index.core.indices.property_graph.transformations.dynamic_llm",
    "llama_index.core.indices.property_graph.transformations.schema_llm",
    "llama_index.core.indices.property_graph.transformations.simple_llm",
    "llama_index.core.instrumentation.events.llm",
    "llama_index.core.llms",
    "llama_index.core.llms.callbacks",
    "llama_index.core.llms.custom",
    "llama_index.core.llms.function_calling",
    "llama_index.core.llms.llm",
    "llama_index.core.llms.mock",
    "llama_index.core.llms.structured_llm",
    "llama_index.core.llms.utils",
    "llama_index.core.multi_modal_llms",
    "llama_index.core.multi_modal_llms.base",
    "llama_index.core.postprocessor.llm_rerank",
    "llama_index.core.postprocessor.structured_llm_rerank",
    "llama_index.core.program.llm_program",
    "llama_index.core.program.multi_modal_llm_program",
    "llama_index.core.question_gen.llm_generators",
    "llama_index.core.selectors.llm_selectors",
    "llama_index.llms",
    "llm",
]

KVSTORE_RELOAD_MODULES = [
    "llama_index.core.storage.kvstore",
    "llama_index.core.storage.kvstore.simple_kvstore",
    "llama_index.core.storage.kvstore.types",
    "pyylmao.handlers.kvstore",
]

NO_MODULE_MATCHES = {
    "commands.bsort",
    "commands.reminders",
    "gpt.billingD",
    "handlers.reloadd",
    "helpres.img2irc",
}


def is_reload_command(text: str) -> bool:
    stripped = text.strip()
    return stripped == "!reload" or stripped.startswith("!reload ") or stripped == "!rehash"


def render_reload_command(text: str) -> list[str]:
    stripped = text.strip()
    if stripped == "!rehash":
        return ["Configuration reloaded successfully"]
    if stripped == "!reload":
        return ["no handler modules found"]
    module = stripped.split(maxsplit=1)[1].strip()
    if not module:
        return ["no handler modules found"]
    if module == "handlers.help":
        return ['Error: TypeError("reload_handlers() got an unexpected keyword argument \'dryrun\'")']
    if module in NO_MODULE_MATCHES:
        return ["no modules found matching query"]
    if module == "commands.urbandict":
        return ["failed:", "- pyylmao.commands.urbandict: parent 'pyylmao.commands' not in sys.modules"]
    if module == "img2irc":
        return [
            "reloaded:",
            "- pyylmao.helpers.img2irc",
            "failed:",
            "- pyylmao.commands.img2irc: parent 'pyylmao.commands' not in sys.modules",
            "- pyylmao.commands.img2irc2: parent 'pyylmao.commands' not in sys.modules",
        ]
    names = reload_module_names(module)
    if not names:
        return ["no modules found matching query"]
    return ["reloaded:"] + [f"- {name}" for name in names]


def reload_module_names(module: str) -> list[str]:
    if module == "llm":
        return LLM_RELOAD_MODULES
    if module == "md2irc":
        return ["pyylmao.helpers.md2irc"]
    if module == "anagram_rs":
        return ["anagram_rs", "anagram_rs.anagram_rs"]
    if module == "kvstore":
        return KVSTORE_RELOAD_MODULES
    if module in {"backends.sqlite", "pyylmao.kv.backends.sqlite"}:
        return ["pyylmao.kv.backends.sqlite"]
    if module == "mdbuffer":
        return ["pyylmao.commands.gpt.mdbuffer"]
    if module.startswith("pyylmao."):
        return [module]
    if module.startswith("helpers."):
        return [f"pyylmao.{module}"]
    if module.startswith("handlers."):
        return [f"pyylmao.{module}"]
    if module.startswith("commands."):
        return [f"pyylmao.{module}"]
    if module.startswith("gpt."):
        return [f"pyylmao.commands.{module}"]
    if "." in module:
        return []
    return []
