const API = "/api";

async function get(path) {
  const r = await fetch(API + path);
  return r.json();
}
async function patch(path, body) {
  const r = await fetch(API + path, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return r.json();
}

function render(html) {
  document.getElementById("app").innerHTML = html;
}

function badgeAI(cls) {
  const labels = {"ai-native": "AI-native", "ai-enabled": "AI-enabled", "non-ai": "Non-AI"};
  const clsLabel = labels[cls] || cls;
  return `<span class="badge badge-${cls}">${clsLabel}</span>`;
}

function gaugeBar(score) {
  if (score == null) return '<div class="gauge"><div class="gauge-fill gauge-low" style="width:0%"></div></div>';
  const cls = score >= 60 ? "gauge-high" : score >= 30 ? "gauge-mid" : "gauge-low";
  return `<div class="gauge"><div class="gauge-fill ${cls}" style="width:${score}%"></div></div>`;
}

function badgeContato(em) {
  if (em) return `<span class="badge badge-contato-sim">Email enviado</span>`;
  return `<span class="badge badge-contato-nao">Não contatado</span>`;
}

window.fecharModal = function() {
  const el = document.querySelector(".modal-overlay");
  if (el) el.remove();
};

async function abrirModalEmail(startupId) {
  let data;
  try {
    data = await get(`/startups/${startupId}`);
  } catch (e) {
    alert("Erro de rede ao carregar dados: " + e.message);
    return;
  }
  if (data.erro) { alert("Erro ao carregar dados: " + data.erro); return; }
  const recs = data.recomendacoes || [];
  const s = data.startup || {};
  const startupNome = s.nome || startupId;
  const topRec = recs.find(r => (r.nivel_prioridade || '').toLowerCase() === 'alta') || recs[0];
  const setor = s.setor || 'tecnologia';
  const func = s.numero_funcionarios_faixa || '';
  const rodada = s.ultima_rodada_valor || '';
  const clientes = '';

  const linhaFunc = func ? `Com ${func} dedicados à inovação` : 'Com uma equipe focada em inovação';
  const linhaRodada = rodada ? `, tendo captado ${rodada}` : '';
  const linhaClientes = clientes ? ` e conquistado ${clientes}` : '';
  const recNome = topRec?.tecnologia || 'soluções NVIDIA';
  const melhEncaixe = topRec?.melhor_encaixe || `acelerar seu ${s.produto_principal || 'produto'} com infraestrutura de IA de alto desempenho`;

  const descProduto = {
    "NVIDIA NIM": "microserviços otimizados para inferência de LLMs e modelos de IA generativa. Reduz latência de resposta de segundos para milissegundos e roda direto no data center da startup sem depender de APIs externas caras.",
    "NVIDIA NIM Microservices": "microserviços otimizados para inferência de LLMs e modelos de IA generativa. Reduz latência de resposta de segundos para milissegundos e roda direto no data center da startup sem depender de APIs externas caras.",
    "NeMo Guardrails": "camada de segurança e governança para agentes de IA. Bloqueia vazamento de dados sensíveis, garante conformidade com LGPD e evita alucinações em chatbots e assistentes virtuais.",
    "NVIDIA RAPIDS": "bibliotecas de código aberto que aceleram processamento de dados tabulares em GPU — até 50x mais rápido que pandas em CPU. Ideal para análise financeira, risco de crédito e detecção de fraudes.",
    "RAPIDS": "bibliotecas de código aberto que aceleram processamento de dados tabulares em GPU — até 50x mais rápido que pandas em CPU. Ideal para análise financeira, risco de crédito e detecção de fraudes.",
    "NVIDIA AI Enterprise": "plataforma completa de IA com governança, monitoramento e segurança para agentes de IA em produção. Inclui suporte enterprise e conformidade regulatória.",
    "NVIDIA Triton": "servidor de inferência que gerencia múltiplos modelos simultaneamente com balanceamento de carga automático. Permite deploy de LLMs, visão computacional e modelos tabulares na mesma infra.",
    "NVIDIA TensorRT": "otimizador de inferência que acelera modelos em até 8x com quantização e fusão de camadas. Reduz custo de hardware e melhora performance em tempo real.",
    "NVIDIA Riva": "plataforma de IA conversacional com ASR e TTS em tempo real. Criação de assistentes de voz com latência abaixo de 300ms e suporte a português brasileiro.",
    "NVIDIA CuOpt": "motor de otimização baseado em GPU para roteirização logística. Resolve problemas de última milha em segundos, reduzindo custos de frete em até 30%.",
    "NVIDIA Isaac": "plataforma de robótica com simulação e treinamento de robôs em ambientes virtuais. Acelera o ciclo de desenvolvimento de robôs autônomos em 10x.",
    "NVIDIA Omniverse": "plataforma de simulação 3D colaborativa para gêmeos digitais. Permite testar cenários industriais, logísticos e de manufatura em ambiente virtual antes de implementar no mundo real."
  };
  const descRec = descProduto[recNome] || 'aceleração de IA com alto desempenho e baixo custo operacional';
  const appRec = {
    "NVIDIA NIM": "atendimento ao cliente com IA generativa, análise de documentos, code assistants e chatbots",
    "NVIDIA NIM Microservices": "atendimento ao cliente com IA generativa, análise de documentos, code assistants e chatbots",
    "NeMo Guardrails": "chatbots seguros, assistentes financeiros, classificação de dados sensíveis",
    "NVIDIA RAPIDS": "análise de risco de crédito, detecção de fraudes, precificação em tempo real",
    "RAPIDS": "análise de risco de crédito, detecção de fraudes, precificação em tempo real",
    "NVIDIA AI Enterprise": "deploy seguro de agentes de IA em produção com governança corporativa",
    "NVIDIA Triton": "servir LLMs, modelos de recomendação e visão computacional em uma única infraestrutura"
  }[recNome] || 'aplicações de IA em produção com performance acelerada';

  const corpo =
    `Olá, equipe ${startupNome},\n\n` +
    `Identificamos que a ${startupNome} está em um momento estratégico no setor de ${setor}. ` +
    `${linhaFunc}${linhaRodada}${linhaClientes}.\n\n` +
    `Segundo nosso radar de inteligência artificial, a ${startupNome} possui um score de fit NVIDIA de ${recs[0]?.score_fit_nvidia || s.score_fit_nvidia || 'elevado'}/100 ` +
    `— indicando que vocês estão prontos para dar o próximo salto com aceleração por GPU.\n\n` +
    `📌 **Recomendação principal: ${recNome}**\n${melhEncaixe}\n\n` +
    `**O que é:** ${descRec}\n\n` +
    `**Aplicações diretas para ${startupNome}:** ${appRec}\n\n` +
    (topRec?.justificativa_negocio ? `${topRec.justificativa_negocio}\n\n` : '') +
    `**Benefícios esperados:**\n` +
    `• Redução de custos de infraestrutura de IA em até 70%\n` +
    `• Aceleração de inferência com latência até 10x menor\n` +
    `• Escalabilidade horizontal sem reengenharia\n` +
    `• Deploy em qualquer ambiente (on-premise, cloud, edge)\n\n` +
    `Gostaria de uma conversa rápida para mostrarmos um POC adaptado à realidade da ${startupNome}?\n\n` +
    `Atenciosamente,\nEquipe NVIDIA Startup Radar`;

  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal-box">
      <h3>Enviar Email para ${startupNome}</h3>
      <label style="font-size:0.8rem;color:#888">Seu email (remetente)</label>
      <input type="email" id="modal-email-remetente" placeholder="seu@email.com" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:12px;font-size:0.85rem">
      <label style="font-size:0.8rem;color:#888">Email da startup (destinatário)</label>
      <input type="email" id="modal-email-dest" placeholder="contato@${startupNome.toLowerCase().replace(/\\s/g,'')}.com.br" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:12px;font-size:0.85rem">
      <label style="font-size:0.8rem;color:#888">Assunto</label>
      <input type="text" id="modal-assunto" value="[NVIDIA] Oportunidade de parceria para ${startupNome}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:12px;font-size:0.85rem">
      <label style="font-size:0.8rem;color:#888">Mensagem (pré-preenchida)</label>
      <textarea id="modal-corpo" rows="12" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:16px;font-size:0.85rem;font-family:inherit">${corpo}</textarea>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-sm" onclick="gerarEmailIA('${startupId}')" id="btn-gerar-ia">🤖 Gerar com IA</button>
        <button class="btn" onclick="abrirGmail()">✉️ Abrir no Gmail</button>
        <button class="btn btn-outline" onclick="copiarTexto()">📋 Copiar texto</button>
        <button class="btn btn-success" onclick="marcarEnviado('${startupId}')">✅ Já enviei</button>
        <button class="btn btn-outline" onclick="fecharModal()">Cancelar</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  window.abrirGmail = function() {
    const dest = document.getElementById("modal-email-dest").value;
    const assunto = document.getElementById("modal-assunto").value;
    const corpo = document.getElementById("modal-corpo").value;
    const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(dest)}&su=${encodeURIComponent(assunto)}&body=${encodeURIComponent(corpo)}`;
    window.open(gmailUrl, "_blank");
  };

  window.copiarTexto = function() {
    const corpo = document.getElementById("modal-corpo").value;
    navigator.clipboard.writeText(corpo);
  };

  window.marcarEnviado = async function(id) {
    const email = document.getElementById("modal-email-dest").value || null;
    await patch(`/startups/${id}/marcar-contato`, { email });
    fecharModal();
    routeCurrentHash();
  };

  window.gerarEmailIA = async function(id) {
    const btn = document.getElementById("btn-gerar-ia");
    btn.disabled = true;
    btn.textContent = "⏳ Gerando...";
    try {
      const res = await fetch(`${API}/startups/${id}/gerar-email`, { method: "POST" });
      const data = await res.json();
      if (data.email) {
        document.getElementById("modal-assunto").value = data.assunto || `[NVIDIA] Oportunidade de parceria`;
        document.getElementById("modal-corpo").value = data.email;
      } else {
        alert("Erro: " + (data.erro || "resposta inválida"));
      }
    } catch (e) {
      alert("Erro ao gerar email: " + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "🤖 Gerar com IA";
    }
  };

  modal.addEventListener("click", e => { if (e.target === modal) fecharModal(); });
}

async function abrirModalEditar(startupId) {
  const data = await get(`/startups/${startupId}`);
  if (data.erro) { alert("Erro: " + data.erro); return; }
  const s = data.startup || {};

  const modal = document.createElement("div");
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal-box" style="max-width:500px">
      <h3>Editar ${s.nome || startupId}</h3>
      <label style="font-size:0.8rem;color:#888">Nome</label>
      <input id="edit-nome" value="${(s.nome||'').replace(/"/g,'&quot;')}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:8px">
      <label style="font-size:0.8rem;color:#888">Website</label>
      <input id="edit-website" value="${(s.website||'').replace(/"/g,'&quot;')}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:8px">
      <label style="font-size:0.8rem;color:#888">Email de Contato</label>
      <input id="edit-email" type="email" value="${(s.email_contato||'').replace(/"/g,'&quot;')}" placeholder="contato@startup.com.br" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:8px">
      <label style="font-size:0.8rem;color:#888">Cidade</label>
      <input id="edit-cidade" value="${(s.cidade||'').replace(/"/g,'&quot;')}" placeholder="São Paulo - SP" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:8px">
      <label style="font-size:0.8rem;color:#888">Setor</label>
      <input id="edit-setor" value="${(s.setor||'').replace(/"/g,'&quot;')}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:8px">
      <label style="font-size:0.8rem;color:#888">Estágio</label>
      <input id="edit-estagio" value="${(s.estagio||'').replace(/"/g,'&quot;')}" placeholder="early/traction/growth/mature" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:8px">
      <label style="font-size:0.8rem;color:#888">Descrição</label>
      <textarea id="edit-descricao" rows="3" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:8px;font-family:inherit">${(s.descricao||'').replace(/"/g,'&quot;')}</textarea>
      <label style="font-size:0.8rem;color:#888">Produto Principal</label>
      <input id="edit-produto" value="${(s.produto_principal||'').replace(/"/g,'&quot;')}" style="width:100%;padding:8px;border:1px solid #ddd;border-radius:6px;margin-bottom:16px">
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-outline" onclick="fecharModal()">Cancelar</button>
        <button class="btn btn-success" onclick="salvarEdicao('${startupId}')">💾 Salvar</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
  modal.addEventListener("click", e => { if (e.target === modal) fecharModal(); });
}

async function salvarEdicao(startupId) {
  const body = {};
  const campos = [
    "nome", "website", "setor", "descricao", "produto_principal",
    "cidade", "estagio", "email"
  ];
  for (const c of campos) {
    const el = document.getElementById(`edit-${c}`);
    if (el) {
      const val = el.value.trim();
      if (val) body[c === "email" ? "email_contato" : c] = val;
      else body[c === "email" ? "email_contato" : c] = null;
    }
  }
  try {
    const r = await fetch(`/api/startups/${startupId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const result = await r.json();
    if (result.erro) {
      alert("Erro: " + result.erro);
    } else {
      fecharModal();
      routeCurrentHash();
    }
  } catch (e) {
    alert("Erro ao salvar: " + e.message);
  }
}

async function reprocessarIncompletas() {
  if (!confirm("Reprocessar startups pendentes (sem email e/ou cidade)?")) return;
  const btn = document.querySelector('[onclick*="reprocessarIncompletas"]');
  if (btn) { btn.disabled = true; btn.textContent = "⏳ Processando..."; }
  try {
    const r = await fetch("/api/reprocessar-incompletas?limite=50", { method: "POST" });
    const result = await r.json();
    alert(`Reprocessamento concluído:\n${result.processadas} processadas\n${result.emails_encontrados} emails encontrados\n${result.cidades_encontradas} cidades encontradas\n${result.sem_email} ainda sem email\n${result.sem_cidade} ainda sem cidade`);
    routeCurrentHash();
  } catch (e) {
    alert("Erro no reprocessamento: " + e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "↻ Reprocessar Pendentes"; }
  }
}

async function renderDashboard() {
  const stats = await get("/stats");
  const filterContato = document.getElementById("filterContato")?.value || "";
  const filterCompletude = document.getElementById("filterCompletude")?.value || "";
  let url = "/startups?limit=10";
  if (filterContato) url += `&contato=${filterContato}`;
  if (filterCompletude === "incompletas") url += `&completude=incompletas`;
  if (filterCompletude === "completas") url += `&completude=completas`;
  const startups = await get(url);

  let rows = startups.startups.map(s => `
    <tr onclick="location.hash='#/startup/${s.id}'">
      <td>${s.nome}</td>
      <td>${s.setor || "-"}</td>
      <td>${badgeAI(s.ai_classification)}</td>
      <td>${gaugeBar(s.score_fit_nvidia)}</td>
      <td>${badgeContato(s.email_enviado_em)}</td>
      <td><button class="btn btn-small" onclick="event.stopPropagation();location.hash='#/briefing/${s.id}'">Briefing</button></td>
    </tr>
  `).join("");

  render(`
    <div class="cards">
      <div class="card"><h3>Total Startups</h3><div class="value">${stats.total_startups}</div></div>
      <div class="card"><h3>AI-native</h3><div class="value">${stats.total_ai_native}</div></div>
      <div class="card"><h3>C/ Recomendação</h3><div class="value">${stats.total_com_recomendacao}</div></div>
      <div class="card"><h3>Score Fit Médio</h3><div class="value">${stats.score_fit_medio}</div></div>
      <div class="card"><h3>Últimas 24h</h3><div class="value">${stats.ultimas_24h}</div></div>
      <div class="card ${stats.incompletas > 0 ? 'card-warning' : ''}"><h3>Pendentes</h3><div class="value">${stats.sem_email || 0} s/ email · ${stats.sem_cidade || 0} s/ cidade</div></div>
    </div>

    <div class="chart-container"><h3>Distribuição por Setor</h3><canvas id="chartSetor" height="80"></canvas></div>

    <div class="filters">
      <div><label>Filtrar</label><select id="filterSetor" onchange="aplicarFiltrosDashboard()">
        <option value="">Todos os setores</option>
        ${stats.distribuicao_setor.map(s => `<option value="${s.setor}">${s.setor}</option>`).join("")}
      </select></div>
      <div><label>Classificação</label><select id="filterClass" onchange="aplicarFiltrosDashboard()">
        <option value="">Todas</option>
        <option value="ai-native">AI-native</option>
        <option value="ai-enabled">AI-enabled</option>
        <option value="non-ai">Non-AI</option>
      </select></div>
      <div><label>Score mínimo</label><input type="number" id="filterScore" min="0" max="100" value="0" onchange="aplicarFiltrosDashboard()" style="width:60px"></div>
      <div><label>Contato</label><select id="filterContato" onchange="renderDashboard()">
        <option value="">Todas</option>
        <option value="sim">Contatadas</option>
        <option value="nao">Não contatadas</option>
      </select></div>
      <div><label>Dados</label><select id="filterCompletude" onchange="renderDashboard()">
        <option value="">Todas</option>
        <option value="incompletas">Pendentes (sem email/cidade)</option>
        <option value="completas">Completas</option>
      </select></div>
      <div><button onclick="aplicarFiltrosDashboard()">Filtrar</button></div>
      <div><a href="/api/export/startups?formato=csv" class="btn">Exportar CSV</a></div>
      <div><button class="btn btn-sm" onclick="reprocessarIncompletas()">↻ Reprocessar Pendentes</button></div>
    </div>

    <table>
      <thead><tr><th>Nome</th><th>Setor</th><th>Classificação</th><th>Score Fit</th><th>Contato</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `);

  if (stats.distribuicao_setor.length) {
    new Chart(document.getElementById("chartSetor"), {
      type: "bar",
      data: {
        labels: stats.distribuicao_setor.map(s => s.setor),
        datasets: [{ label: "Startups", data: stats.distribuicao_setor.map(s => s.total), backgroundColor: "#76b900" }]
      },
      options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
    });
  }
}

async function aplicarFiltrosDashboard() {
  const setor = document.getElementById("filterSetor").value;
  const cls = document.getElementById("filterClass").value;
  const score = document.getElementById("filterScore").value;
  const contato = document.getElementById("filterContato").value;
  const completude = document.getElementById("filterCompletude")?.value || "";
  let url = "/startups?limit=100";
  if (setor) url += `&setor=${setor}`;
  if (cls) url += `&classificacao=${cls}`;
  if (score) url += `&score_fit_min=${score}`;
  if (contato) url += `&contato=${contato}`;
  if (completude === "incompletas") url += `&completude=incompletas`;
  if (completude === "completas") url += `&completude=completas`;

  const data = await get(url);
  let rows = data.startups.map(s => `
    <tr onclick="location.hash='#/startup/${s.id}'">
      <td>${s.nome}</td>
      <td>${s.setor || "-"}</td>
      <td>${badgeAI(s.ai_classification)}</td>
      <td>${gaugeBar(s.score_fit_nvidia)}</td>
      <td>${badgeContato(s.email_enviado_em)}</td>
      <td><button class="btn btn-small" onclick="event.stopPropagation();location.hash='#/briefing/${s.id}'">Briefing</button></td>
    </tr>
  `).join("");

  document.querySelector("table tbody").innerHTML = rows || "<tr><td colspan='6' style='text-align:center;padding:24px'>Nenhuma startup encontrada</td></tr>";
}

async function renderStartup(id) {
  const data = await get(`/startups/${id}`);
  if (data.erro) return render(`<div class="detail"><h2>Erro</h2><p>${data.erro}</p></div>`);

  const s = data.startup;
  const c = data.classificacao || {};
  const recs = data.recomendacoes || [];

  const recsAlta = recs.filter(r => (r.nivel_prioridade || '').toLowerCase() === 'alta' && r.melhor_encaixe).slice(0, 3);
  let recHTML = recsAlta.map(r => `
    <div class="rec-card">
      <div class="rec-header">
        <span class="rec-rank">#${r.rank}</span>
        <strong>${r.tecnologia}</strong>
        <span class="rec-prio rec-prio-alta">${r.nivel_prioridade}</span>
        <span class="rec-complex">${r.complexidade_implementacao}</span>
      </div>
      <div class="rec-body">
        ${r.melhor_encaixe ? `<div class="rec-section rec-encaixe"><div class="rec-label">🎯 Melhor Encaixe</div><p>${r.melhor_encaixe}</p></div>` : ''}
        <div class="rec-section"><div class="rec-label">Justificativa Técnica</div><p>${r.justificativa_tecnica}</p></div>
        <div class="rec-section"><div class="rec-label">Justificativa de Negócio</div><p>${r.justificativa_negocio}</p></div>
        <div class="rec-section"><div class="rec-label">Próxima Ação</div><p>${r.proxima_acao_sugerida}</p></div>
        ${r.url_referencia ? `<div class="rec-section"><a href="${r.url_referencia}" target="_blank" rel="noopener" class="btn btn-sm">Ver Referência</a></div>` : ''}
      </div>
    </div>
  `).join("") || (recs.length ? "<p style='color:#888'>Nenhuma recomendação de prioridade alta.</p>" : "<p>Nenhuma recomendação gerada ainda.</p>");

  render(`
    <button class="btn mb-16" onclick="location.hash='#/'">← Voltar</button>
    <div class="detail">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <h2>${s.nome}</h2>
        ${badgeContato(s.email_enviado_em)}
      </div>
      <div class="detail-grid">
        <dt>Website</dt><dd>${s.website || "-"}</dd>
        <dt>Setor</dt><dd>${s.setor || "-"}</dd>
        <dt>Cidade</dt><dd>${s.cidade || "-"}</dd>
        <dt>Estágio</dt><dd>${s.estagio || "-"}</dd>
        <dt>Email</dt><dd>${s.email_contato || "-"}</dd>
        <dt>Descrição</dt><dd>${s.descricao || "-"}</dd>
        <dt>Produto Principal</dt><dd>${s.produto_principal || "-"}</dd>
      </div>

      <h3>Classificação</h3>
      <div class="detail-grid">
        <dt>Tipo IA</dt><dd>${badgeAI(c.ai_classification)}</dd>
        <dt>Ramo</dt><dd>${c.ramo_principal || "-"}</dd>
        <dt>Score Fit NVIDIA</dt><dd>${c.score_fit_nvidia != null ? `${c.score_fit_nvidia}/100` : "-"} ${gaugeBar(c.score_fit_nvidia)}</dd>
        <dt>Usa NVIDIA</dt><dd>${c.usa_nvidia ? "Sim" : "Não"}</dd>
      </div>

      <h3>Recomendações Prioritárias</h3>
      ${recHTML}

      <div style="display:flex;gap:8px;margin-top:16px;flex-wrap:wrap">
        ${data.briefing_id ? `<a href="#/briefing/${id}" class="btn">Ver Briefing Completo</a>` : ""}
        <button class="btn" onclick="abrirModalEmail('${id}')">📧 Enviar Email</button>
        <button class="btn btn-outline" onclick="abrirModalEditar('${id}')">✏️ Editar</button>
        ${s.email_enviado_em ? "" : `<button class="btn btn-success btn-sm" onclick="patch('/startups/${id}/marcar-contato',{}).then(()=>routeCurrentHash())">✅ Já enviei</button>`}
      </div>
    </div>
  `);
}

async function renderStartups() {
  const contato = document.getElementById("filterContatoLista")?.value || "";
  let url = "/startups?limit=200";
  if (contato) url += `&contato=${contato}`;
  const data = await get(url);
  let rows = data.startups.map(s => `
    <tr onclick="location.hash='#/startup/${s.id}'">
      <td>${s.nome}</td>
      <td>${s.setor || "-"}</td>
      <td>${s.cidade || "-"}</td>
      <td>${badgeAI(s.ai_classification)}</td>
      <td>${gaugeBar(s.score_fit_nvidia)}</td>
      <td>${s.estagio || "-"}</td>
      <td>${badgeContato(s.email_enviado_em)}</td>
    </tr>
  `).join("");

  render(`
    <h2 class="mb-16">Todas as Startups</h2>
    <div class="filters">
      <div><label>Contato</label><select id="filterContatoLista" onchange="renderStartups()">
        <option value="">Todas</option>
        <option value="sim"${contato==='sim'?' selected':''}>Contatadas</option>
        <option value="nao"${contato==='nao'?' selected':''}>Não contatadas</option>
      </select></div>
    </div>
    <table>
      <thead><tr><th>Nome</th><th>Setor</th><th>Cidade</th><th>Classificação</th><th>Score Fit</th><th>Estágio</th><th>Contato</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="7" style="text-align:center;padding:24px">Nenhuma startup cadastrada</td></tr>'}</tbody>
    </table>
  `);
}

async function renderBriefing(startupId) {
  const data = await get(`/startups/${startupId}/briefing`);
  if (data.erro || !data.conteudo_json) return render(`<div class="detail"><h2>Briefing não disponível</h2><p>Execute o pipeline para gerar o briefing desta startup.</p><button class="btn mt-12" onclick="location.hash='#/startup/${startupId}'">Voltar</button></div>`);

  let json;
  try {
    json = typeof data.conteudo_json === "string" ? JSON.parse(data.conteudo_json) : data.conteudo_json;
  } catch (e) {
    json = null;
  }
  if (!json) return render(`<div class="detail"><h2>Briefing corrompido</h2><p>Os dados do briefing estão em formato inválido. Execute o pipeline novamente.</p><button class="btn mt-12" onclick="location.hash='#/startup/${startupId}'">Voltar</button></div>`);

  const s = json.startup || {};
  const p = json.perfil_ia || {};
  const evs = json.evidencias_chave || [];
  const gaps = json.gaps_tecnicos || [];
  const recs = json.recomendacoes_nvidia || [];

  const scoreColor = (score) => {
    if (score >= 80) return '#22c55e';
    if (score >= 50) return '#eab308';
    return '#ef4444';
  };

  const escHtml = (str) => {
    if (str == null) return '-';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  };

  const evHtml = evs.map(ev => `
    <div class="evidencia-item">
      <span class="evidencia-tipo">${escHtml(ev.tipo)}</span>
      ${ev.url ? `<a href="${escHtml(ev.url)}" target="_blank" rel="noopener">${escHtml(ev.titulo || ev.url)}</a>` : escHtml(ev.titulo || 'Sem título')}
      ${ev.score != null ? `<span class="evidencia-score">${ev.score}</span>` : ''}
    </div>
  `).join('');

  const gapHtml = gaps.length ? gaps.map(g => `<li>${escHtml(g)}</li>`).join('') : '<li style="color:#888">Nenhum gap técnico identificado</li>';

  const recsAlta = recs.filter(r => (r.nivel_prioridade || '').toLowerCase() === 'alta' && r.melhor_encaixe).slice(0, 3);
  const recHtml = recsAlta.map(r => `
    <div class="rec-card">
      <div class="rec-header">
        <span class="rec-rank">#${escHtml(r.rank)}</span>
        <strong class="rec-tec">${escHtml(r.tecnologia)}</strong>
        <span class="rec-prio rec-prio-alta">${escHtml(r.nivel_prioridade)}</span>
        <span class="rec-complex">${escHtml(r.complexidade_implementacao)}</span>
      </div>
      <div class="rec-body">
        ${r.melhor_encaixe ? `<div class="rec-section rec-encaixe"><div class="rec-label">🎯 Melhor Encaixe</div><p>${escHtml(r.melhor_encaixe)}</p></div>` : ''}
        <div class="rec-section"><div class="rec-label">Justificativa Técnica</div><p>${escHtml(r.justificativa_tecnica)}</p></div>
        <div class="rec-section"><div class="rec-label">Justificativa de Negócio</div><p>${escHtml(r.justificativa_negocio)}</p></div>
        <div class="rec-section"><div class="rec-label">Próxima Ação</div><p>${escHtml(r.proxima_acao_sugerida)}</p></div>
        ${r.url_referencia ? `<div class="rec-section"><a href="${escHtml(r.url_referencia)}" target="_blank" rel="noopener" class="btn btn-sm">Ver Referência</a></div>` : ''}
        ${r.evidencias_usadas?.length ? `<div class="rec-section"><div class="rec-label">Evidências</div><ul class="rec-ev-list">${r.evidencias_usadas.map(u => `<li><a href="${escHtml(u)}" target="_blank" rel="noopener">${escHtml(u)}</a></li>`).join('')}</ul></div>` : ''}
      </div>
    </div>
  `).join('');

  render(`
    <button class="btn mb-16" onclick="location.hash='#/startup/${startupId}'">← Voltar</button>

    <div class="detail briefing-page">

      <div class="b-header">
        <div>
          <h2>${escHtml(s.nome || startupId)}</h2>
          <p class="b-subtitle">${escHtml(s.setor || '')}${s.website ? ` · <a href="${escHtml(s.website)}" target="_blank" rel="noopener">${escHtml(s.website)}</a>` : ''}</p>
        </div>
        <div class="b-score" style="--score-color:${scoreColor(p.score_fit_nvidia)}">
          <div class="b-score-value">${p.score_fit_nvidia != null ? escHtml(p.score_fit_nvidia) : '-'}</div>
          <div class="b-score-label">Fit NVIDIA</div>
        </div>
      </div>

      <div class="b-grid">
        <div class="b-card">
          <h3>Dados da Startup</h3>
          <table class="b-info-table">
            <tr><td>Estágio</td><td>${escHtml(s.estagio)}</td></tr>
            <tr><td>Cidade</td><td>${escHtml(s.cidade)}</td></tr>
            <tr><td>Descrição</td><td>${escHtml(s.descricao)}</td></tr>
            <tr><td>Produto Principal</td><td>${escHtml(s.produto_principal)}</td></tr>
          </table>
        </div>

        <div class="b-card">
          <h3>Perfil de IA</h3>
          <div class="b-perfil">
            <div class="b-perfil-item">
              <span class="b-perfil-label">Classificação</span>
              <span class="b-perfil-value badge-${escHtml((p.classificacao || '').toLowerCase().replace(/[^a-z0-9]/g,''))}">${escHtml(p.classificacao)}</span>
            </div>
            <div class="b-perfil-item">
              <span class="b-perfil-label">Ramo</span>
              <span class="b-perfil-value">${escHtml(p.ramo)}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="b-card">
        <h3>Gaps Técnicos Identificados</h3>
        <ul class="b-gaps-list">${gapHtml}</ul>
      </div>

      ${evs.length ? `
      <div class="b-card">
        <h3>Evidências Coletadas <span class="b-count">${evs.length}</span></h3>
        <div class="b-evidencias">${evHtml}</div>
      </div>` : ''}

      ${recsAlta.length ? `
      <div class="b-card">
        <h3>Recomendações NVIDIA Prioritárias <span class="b-count">${recsAlta.length}</span></h3>
        ${recs.length > recsAlta.length ? `<p style="font-size:0.78rem;color:#888;margin:-8px 0 12px 0">Mostrando as ${recsAlta.length} recomendações de melhor encaixe (${recs.length - recsAlta.length} ocultas)</p>` : ''}
        <div class="b-recs">${recHtml}</div>
      </div>` : (recs.length ? `<div class="b-card"><h3>Recomendações NVIDIA</h3><p style="color:#888">Nenhuma recomendação de prioridade alta disponível.</p></div>` : '')}

      <div class="b-card">
        <h3>Resumo Executivo</h3>
        <p class="b-resumo">${escHtml(json.resumo_executivo || '')}</p>
      </div>

      <div class="b-footer">
        <span class="b-gerado">Gerado em: ${escHtml(json.gerado_em || '')}</span>
        <div style="display:flex;gap:8px">
          <a href="/api/export/briefing/${data.id}?formato=json" class="btn btn-sm">Exportar JSON</a>
          <button class="btn btn-sm" onclick="abrirModalEmail('${startupId}')">📧 Enviar Email</button>
        </div>
      </div>

    </div>
  `);
}

let _hashBusy = false;

function navigateHash(hash) {
  _hashBusy = true;
  location.hash = hash;
  _hashBusy = false;
}

document.addEventListener("click", e => {
  const link = e.target.closest("[data-page]");
  if (!link) return;
  e.preventDefault();
  const page = link.dataset.page;
  if (page === "dashboard") navigateHash("#/");
  if (page === "startups") navigateHash("#/startups");
  if (page === "contatadas") navigateHash("#/contatadas");
  if (page === "nao-contatadas") navigateHash("#/nao-contatadas");
});

async function renderContatoPage(contatoFilter, titulo) {
  const data = await get(`/startups?limit=200&contato=${contatoFilter}`);
  let rows = data.startups.map(s => `
    <tr onclick="location.hash='#/startup/${s.id}'">
      <td>${s.nome}</td>
      <td>${s.setor || "-"}</td>
      <td>${s.cidade || "-"}</td>
      <td>${badgeAI(s.ai_classification)}</td>
      <td>${gaugeBar(s.score_fit_nvidia)}</td>
      <td>${s.estagio || "-"}</td>
      <td>${badgeContato(s.email_enviado_em)}</td>
    </tr>
  `).join("");

  render(`
    <h2 class="mb-16">${titulo}</h2>
    <table>
      <thead><tr><th>Nome</th><th>Setor</th><th>Cidade</th><th>Classificação</th><th>Score Fit</th><th>Estágio</th><th>Contato</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="7" style="text-align:center;padding:24px">Nenhuma startup encontrada</td></tr>'}</tbody>
    </table>
  `);
}

function routeCurrentHash() {
  const hash = location.hash.slice(1) || "/";
  const m = hash.match(/^\/startup\/(.+)/);
  if (m) return renderStartup(m[1]);
  const b = hash.match(/^\/briefing\/(.+)/);
  if (b) return renderBriefing(b[1]);
  if (hash === "/startups") return renderStartups();
  if (hash === "/contatadas") return renderContatoPage("sim", "Startups Contatadas");
  if (hash === "/nao-contatadas") return renderContatoPage("nao", "Startups Não Contatadas");
  renderDashboard();
}

window.addEventListener("hashchange", () => {
  if (_hashBusy) return;
  routeCurrentHash();
});

routeCurrentHash();
