"""Credential removal for logs transferred to the competition website."""
import re

LOG_SOURCES = {'worker', 'agent', 'controller', 'diagnostics', 'environment'}
MAX_LOG_CHUNK = 64 * 1024


def redact_log(text, secrets=()):
    for value in sorted((value for value in secrets if isinstance(value, str) and value), key=len, reverse=True):
        text = text.replace(value, '[REDACTED]')
    text = re.sub(r'-----BEGIN [^\n]*PRIVATE KEY-----[\s\S]*?-----END [^\n]*PRIVATE KEY-----', '[PRIVATE KEY REDACTED]', text)
    text = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9_./+\-=]+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)(https?://)[^\s/:]+:[^\s/@]+@', r'\1[REDACTED]@', text)
    text = re.sub(r'\b(?:github_pat_|gh[pousr]_|hf_|sk-|re_)[A-Za-z0-9_-]{20,}\b', '[REDACTED]', text)
    text = re.sub(r'\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED]', text)
    text = re.sub(r'''(?i)((?:api[_-]?(?:key|token)|access[_-]?token|password|passwd|secret|x-evaluation-(?:api-token|lease))['"]?\s*[:=]\s*['"]?)(?!\[REDACTED\])[^\s,'"}\]]+''', r'\1[REDACTED]', text)
    return text


def redact_evaluation_details(text):
    """Remove hidden evaluation inputs while retaining diagnostic messages."""
    text = re.sub(r'''(?i)((?:world[_-]?seed|seed|init_state_id|hidden_label|ground_truth|target_class|manifest_sha256|sample_id)['"]?\s*[:=]\s*['"]?)(?!\[HIDDEN\])(?:\[[^\]\n]*\]|[^\s,'"}\]]+)''', r'\1[HIDDEN]', text)
    text = re.sub(r'(?i)(<(?:Seed|WorldSeed)>)[^<]+(</(?:Seed|WorldSeed)>)', r'\1[HIDDEN]\2', text)
    return text
