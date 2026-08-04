# Empresas bloqueadas pelo Cloudflare

Empresas marcadas com `revisao_manual = true` no Supabase foram bloqueadas pelo
Cloudflare durante a coleta automática do `descobre_institucional.py`.

O scraper detecta a página de challenge ("Just a moment...", "Ray ID") e, em vez
de registrar um falso negativo em `sinais_ia`, marca a empresa para revisão e pula.
Em execuções futuras essas empresas aparecem como `[skip] revisão manual pendente`.

---

## Como revisar manualmente

1. Abra o site da empresa no browser normalmente
2. Busque por sinais de IA: "inteligência artificial", "machine learning", "LLM",
   "modelo", "visão computacional", etc.
3. Atualize o Supabase conforme o resultado:

**Se encontrou sinal de IA:**
```sql
INSERT INTO sinais_ia (empresa_id, camada, encontrado, evidencia, fonte_url)
VALUES (<id>, 'institucional', true, '<trecho encontrado>', '<url>');

UPDATE empresas SET revisao_manual = false WHERE id = <id>;
```

**Se não encontrou sinal de IA:**
```sql
INSERT INTO sinais_ia (empresa_id, camada, encontrado, evidencia, fonte_url)
VALUES (<id>, 'institucional', false, null, 'https://<dominio>');

UPDATE empresas SET revisao_manual = false WHERE id = <id>;
```

---

## Empresas bloqueadas conhecidas

| Empresa | Domínio | Observação |
|---------|---------|------------|
| Idwall  | idwall.com | Site 100% JS + Cloudflare |
