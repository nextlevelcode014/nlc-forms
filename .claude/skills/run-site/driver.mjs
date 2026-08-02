#!/usr/bin/env bun
/**
 * Driver de verificação visual dos frontends do nlc-forms — zero dependências.
 *
 * Fala CDP (Chrome DevTools Protocol) direto por WebSocket, em vez de usar
 * Playwright ou Puppeteer: o frontend inteiro tem uma dependência de runtime
 * (astro) e instalar ~300MB de navegador só para tirar screenshot seria peso
 * desproporcional. O bun já traz fetch e WebSocket, então o driver cabe aqui.
 *
 *   bun .claude/skills/run-site/driver.mjs audit --projeto public --destravar
 *   bun .claude/skills/run-site/driver.mjs shot /triagem-suporte.html --destravar --out /tmp/s.png
 *   bun .claude/skills/run-site/driver.mjs eval / "document.title"
 *
 * Requer um servidor já no ar (ver SKILL.md) e um binário Chromium.
 */
import { spawn } from 'node:child_process';
import { mkdir, writeFile, rm, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';

// ---------------------------------------------------------------- CLI (parsing)

// Flags que consomem o argumento seguinte. Sem esta lista, `--destravar /x.html`
// perderia a rota: o parser antigo descartava todo argumento precedido de flag,
// então qualquer flag booleana engolia o posicional seguinte em silêncio.
const FLAGS_COM_VALOR = new Set([
  'width',
  'height',
  'theme',
  'out',
  'scroll-to',
  'token',
  'admin-key',
  'projeto',
  'dist',
]);

const [comando, ...resto] = process.argv.slice(2);

const valores = new Map();
const booleanas = new Set();
const posicionais = [];
for (let i = 0; i < resto.length; i++) {
  const arg = resto[i];
  if (!arg.startsWith('--')) {
    posicionais.push(arg);
    continue;
  }
  const nome = arg.slice(2);
  if (FLAGS_COM_VALOR.has(nome)) valores.set(nome, resto[++i]);
  else booleanas.add(nome);
}

const flag = (nome, padrao) => valores.get(nome) ?? padrao;
const ligada = (nome) => booleanas.has(nome);

const largura = Number(flag('width', 1440));
const altura = Number(flag('height', 900));
const tema = flag('theme', 'dark');
const projeto = flag('projeto', 'public');

if (!['public', 'admin'].includes(projeto)) {
  console.error(`--projeto precisa ser "public" ou "admin" (recebi "${projeto}")`);
  process.exit(1);
}

// Cada projeto tem a sua porta: 4321 o público, 9080 o painel — as mesmas do
// .env.example, porque são elas que o ALLOWED_ORIGINS da API libera.
const PORTA_PADRAO = { public: 4321, admin: 9080 };
const BASE = process.env.SITE_URL ?? `http://localhost:${PORTA_PADRAO[projeto]}`;
const DIST = flag('dist', `frontend/${projeto}/dist`);

// Ordem de preferência. O primeiro que existir vence; BROWSER_BIN sobrepõe tudo.
const CANDIDATOS = [
  process.env.BROWSER_BIN,
  '/opt/google/chrome/chrome',
  '/usr/bin/chromium',
  '/usr/bin/google-chrome',
  '/opt/brave.com/brave-origin-beta/brave',
].filter(Boolean);

function acharNavegador() {
  const bin = CANDIDATOS.find((c) => existsSync(c));
  if (!bin) {
    console.error(
      'Nenhum Chromium encontrado. Testei:\n  ' +
        CANDIDATOS.join('\n  ') +
        '\nDefina BROWSER_BIN=/caminho/do/binario.',
    );
    process.exit(1);
  }
  return bin;
}

/** Sobe o navegador headless e devolve { porta, encerrar }. */
async function abrirNavegador() {
  const perfil = `/tmp/nlc-driver-${process.pid}`;
  const proc = spawn(
    acharNavegador(),
    [
      '--headless',
      '--remote-debugging-port=0', // porta 0 = o sistema escolhe; evita colisão
      `--user-data-dir=${perfil}`,
      '--hide-scrollbars',
      '--disable-gpu',
      '--force-color-profile=srgb',
      'about:blank',
    ],
    { stdio: ['ignore', 'pipe', 'pipe'] },
  );

  // A porta escolhida só aparece no stderr, na linha "DevTools listening on ws://…"
  const porta = await new Promise((resolve, reject) => {
    const prazo = setTimeout(() => reject(new Error('navegador não subiu em 20s')), 20_000);
    let buffer = '';
    proc.stderr.on('data', (d) => {
      buffer += d;
      const m = buffer.match(/ws:\/\/127\.0\.0\.1:(\d+)\//);
      if (m) {
        clearTimeout(prazo);
        resolve(Number(m[1]));
      }
    });
    proc.on('exit', (c) => reject(new Error(`navegador saiu com código ${c}\n${buffer}`)));
  });

  return {
    porta,
    async encerrar() {
      proc.kill();
      await rm(perfil, { recursive: true, force: true }).catch(() => {});
    },
  };
}

/** Cria uma aba e devolve um cliente CDP com `send(metodo, params)`. */
async function abrirAba(porta) {
  // Chrome novo exige PUT em /json/new; versões antigas aceitam GET.
  let alvo = await fetch(`http://127.0.0.1:${porta}/json/new?about:blank`, { method: 'PUT' })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  if (!alvo) {
    alvo = await fetch(`http://127.0.0.1:${porta}/json/new?about:blank`).then((r) => r.json());
  }

  const ws = new WebSocket(alvo.webSocketDebuggerUrl);
  await new Promise((ok, err) => {
    ws.onopen = ok;
    ws.onerror = () => err(new Error('não consegui abrir o WebSocket do CDP'));
  });

  let id = 0;
  const pendentes = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    const p = pendentes.get(msg.id);
    if (!p) return; // evento, não resposta
    pendentes.delete(msg.id);
    msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result);
  };

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const meu = ++id;
      pendentes.set(meu, { resolve, reject });
      ws.send(JSON.stringify({ id: meu, method, params }));
    });

  await send('Page.enable');
  await send('Runtime.enable');
  return { send, fechar: () => ws.close() };
}

async function avaliar(cli, expressao, { esperar = false } = {}) {
  const r = await cli.send('Runtime.evaluate', {
    expression: esperar
      ? `(async () => { try { return JSON.stringify(await (${expressao})) } catch (e) { return JSON.stringify(String(e)) } })()`
      : `(() => { try { return JSON.stringify(${expressao}) } catch (e) { return JSON.stringify(String(e)) } })()`,
    returnByValue: true,
    awaitPromise: esperar,
    timeout: 20_000,
  });
  return JSON.parse(r.result.value ?? 'null');
}

// ---------------------------------------------------------------- portões

/**
 * Abre os portões de acesso **pelo DOM**, sem API e sem credencial.
 *
 * Toda página com conteúdo neste projeto é gated: a triagem só monta o
 * formulário depois de validar o token, e o painel só revela `#protegido`
 * depois da chave de admin. Sem isto a auditoria fotografa a tela de bloqueio e
 * reporta sucesso — o mesmo erro de auditar um 404 achando que é uma página.
 *
 * Vale para conferir layout e contraste. O conteúdo que vem da API (lista de
 * clientes, dados da triagem) continua vazio — para isso use --admin-key com a
 * API no ar.
 */
const DESTRAVAR = `(() => {
  const esconder = (id) => { const e = document.getElementById(id); if (e) e.hidden = true; };
  const mostrar = (id) => { const e = document.getElementById(id); if (e) { e.hidden = false; return true } return false };
  esconder('verificando'); esconder('bloqueado'); esconder('portao');
  return [mostrar('conteudo'), mostrar('protegido')].some(Boolean);
})()`;

/** Espera o portão parar de piscar: `#verificando` só some quando o fetch volta. */
const GATE_ASSENTOU = `new Promise(pronto => {
  const alvo = document.getElementById('verificando');
  if (!alvo || alvo.hidden) return pronto(true);
  const prazo = setTimeout(() => pronto(false), 8000);
  const obs = new MutationObserver(() => {
    if (alvo.hidden) { clearTimeout(prazo); obs.disconnect(); pronto(true) }
  });
  obs.observe(alvo, { attributes: true, attributeFilter: ['hidden'] });
})`;

/** Login de verdade no painel: digita a chave e espera `#protegido` aparecer. */
const entrarAdmin = (chave) => `(async () => {
  const campo = document.getElementById('chave-admin');
  const botao = document.getElementById('btn-entrar');
  if (!campo || !botao) return 'sem portão nesta página';
  campo.value = ${JSON.stringify(chave)};
  botao.click();
  for (let i = 0; i < 100; i++) {
    const p = document.getElementById('protegido');
    if (p && !p.hidden) return true;
    const erro = document.getElementById('feedback-login');
    if (erro?.textContent?.trim()) return erro.textContent.trim();
    await new Promise(r => setTimeout(r, 100));
  }
  return 'tempo esgotado esperando o painel abrir';
})()`;

// ---------------------------------------------------------------- preparação

/**
 * Roda de novo se a página trocar de contexto no meio.
 *
 * `painel-atendimento.html` é uma ponte que faz `location.replace('/')` no
 * <head>: o contexto de execução morre durante o `document.fonts.ready` e o CDP
 * responde "Inspected target navigated or closed". Sem esta tolerância o driver
 * inteiro caía nessa rota — e ela está no dist/, então caía em toda auditoria do
 * painel. Na segunda tentativa já estamos no destino, e quem decide o que fazer
 * com o redirecionamento é o chamador.
 */
const NAVEGOU = /navigated or closed|context was destroyed|Cannot find context/i;
async function tolerante(fn) {
  try {
    return await fn();
  } catch (erro) {
    if (!NAVEGOU.test(String(erro?.message))) throw erro;
    await new Promise((r) => setTimeout(r, 400));
    return await fn();
  }
}

/** Navega, aplica viewport e tema, espera fonte, resolve portões, congela. */
async function preparar(cli, rota, opcoes = {}) {
  const { rolarAte, congelar = true, destravar = false, token = null, adminKey = null } = opcoes;

  await cli.send('Emulation.setDeviceMetricsOverride', {
    width: largura,
    height: altura,
    deviceScaleFactor: 1,
    mobile: largura < 640,
  });

  let url = rota.startsWith('http') ? rota : BASE + rota;
  // O token vai na query porque é de lá que o FormularioTriagem lê
  // (`new URLSearchParams(location.search).get('token')`).
  if (token && !url.includes('token=')) {
    url += (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token);
  }

  const r = await cli.send('Page.navigate', { url });

  // Sem isto o driver "tem sucesso" fotografando a tela de erro do Chromium:
  // Page.navigate resolve normalmente e só sinaliza a falha em errorText.
  if (r.errorText) {
    throw new Error(
      `${url} não carregou: ${r.errorText}\n` +
        'O servidor está no ar? Veja a seção Run do SKILL.md.',
    );
  }

  await tolerante(async () => {
    // `document.fonts.ready` é o sinal certo: sem ele o screenshot sai com a
    // fonte de fallback e o layout mede diferente.
    await cli.send('Runtime.evaluate', {
      expression: `new Promise(r => {
        const pronto = () => document.fonts.ready.then(r);
        document.readyState === 'complete' ? pronto() : addEventListener('load', pronto);
      })`,
      awaitPromise: true,
      timeout: 20_000,
    });

    // Congelar vem ANTES de trocar o tema, e é uma ordem que custou a aparecer:
    // `.btn` e companhia têm `transition: background .2s`, então medir logo
    // depois do `data-theme` pegava a cor no meio da transição. O contraste do
    // rodapé oscilava entre 4,13 e 4,26 e a mesma auditoria achava 7 ou 15
    // problemas conforme a máquina estivesse mais ou menos ocupada. Congelado
    // primeiro, a troca de tema é instantânea e a medição é determinística.
    // A regra é global e vale também para o que o --destravar revelar depois.
    if (congelar) {
      await cli.send('Runtime.evaluate', {
        expression: `(() => {
          const s = document.createElement('style');
          s.textContent = \`*, *::before, *::after {
            animation-duration: 0s !important;
            animation-delay: 0s !important;
            transition-duration: 0s !important;
            transition-delay: 0s !important;
          }\`;
          document.head.appendChild(s);
        })()`,
      });
    }

    if (tema) {
      // `data-theme` no <html> é o único interruptor: tokens.css troca o
      // `color-scheme` por ele e todo o resto sai do `light-dark()`. Não há
      // persistência em localStorage neste projeto — e não deve haver.
      await cli.send('Runtime.evaluate', {
        expression: `document.documentElement.dataset.theme = ${JSON.stringify(tema)}`,
      });
    }

    // O script da triagem decide o estado depois de um fetch; destravar antes
    // disso seria desfeito pelo `bloquear()` que chega em seguida.
    await avaliar(cli, GATE_ASSENTOU, { esperar: true });

    if (adminKey) {
      const res = await avaliar(cli, entrarAdmin(adminKey), { esperar: true });
      if (res !== true) throw new Error(`login de admin falhou: ${res}`);
      await new Promise((r) => setTimeout(r, 400)); // deixa a lista chegar
    } else if (destravar) {
      await avaliar(cli, DESTRAVAR);
    }
  });

  if (rolarAte) {
    const achou = await avaliar(
      cli,
      `(() => {
        const el = document.querySelector(${JSON.stringify(rolarAte)});
        if (!el) return false;
        el.scrollIntoView({ block: 'center', behavior: 'instant' });
        return true;
      })()`,
    );
    if (!achou) throw new Error(`nenhum elemento casa com "${rolarAte}"`);
  }

  // Redirecionamento (painel-atendimento.html manda para /) — auditar o destino
  // no lugar da rota pedida seria contar a mesma página duas vezes.
  return await avaliar(cli, 'location.pathname');
}

// ---------------------------------------------------------------- auditoria

/**
 * Checagens que nem o build nem o `astro check` pegam, porque só existem depois
 * do CSS resolver e do JS rodar.
 *
 * `aberto` diz se os portões foram destravados: sem isso não dá para saber se
 * ver o formulário na tela é bug de vazamento ou efeito do --destravar.
 */
const auditoria = (aberto) => `(() => {
  const p = [];
  const de = document.documentElement;

  if (de.scrollWidth > innerWidth + 1)
    p.push('rolagem horizontal: ' + de.scrollWidth + 'px > ' + innerWidth + 'px');

  // ── Portão ────────────────────────────────────────────────
  // O conteúdo protegido não pode existir visível sem credencial. Vale para os
  // dois lados: a triagem promete que "quem chega sem link não vê nem a
  // estrutura das perguntas", e o painel lê dados de cliente.
  if (!${aberto}) {
    for (const id of ['conteudo', 'protegido']) {
      const el = document.getElementById(id);
      if (el && !el.hidden && el.getBoundingClientRect().height > 0)
        p.push('portão vazado: #' + id + ' visível sem credencial');
    }
  }

  // ── Palavras coladas ──────────────────────────────────────
  // O Astro descarta o espaço antes de uma tag inline quando há quebra de linha
  // no .astro. É o erro mais comum de template neste stack.
  // A lista já deixou passar um caso real: "algo comoNLC-XXXX-XXXX" numa <li>
  // com <span>, que não estava coberta. Agora vale para qualquer filho inline
  // dos contêineres de texto, em vez de uma lista de pares mantida à mão.
  // Espaço posto no CSS conta como espaço. O .secao__num separa o "01" do
  // título com margin-right, e sem esta ressalva a checagem acusava doze
  // "palavras coladas" que na tela estão perfeitamente separadas — ruído que
  // faz a auditoria inteira perder credibilidade.
  const folga = (el, lado) => {
    const cs = getComputedStyle(el);
    return parseFloat(cs['margin' + lado]) > 1 || parseFloat(cs['padding' + lado]) > 1;
  };

  document.querySelectorAll('p :is(a,strong,em,code,span,b,i), li :is(a,strong,em,code,span,b,i), h1 span, label span').forEach(el => {
    if (getComputedStyle(el).display !== 'inline') return; // bloco já quebra linha
    const antes = el.previousSibling, depois = el.nextSibling, t = el.textContent;
    // Uma letra só abrindo a palavra é destaque de sigla, não espaço perdido.
    const sigla = t.length === 1 &&
      (!antes || antes.nodeType !== 3 || /[^\\p{L}\\p{N}]$/u.test(antes.textContent));
    // Letra colada em letra, e também pontuação de fim de trecho colada em
    // palavra: "inegociáveis:liberdade" passava porque ":" não é letra. Abre
    // parêntese, aspas e cifrão ficam de fora — esses grudam de propósito.
    if (!folga(el, 'Left') && antes?.nodeType === 3 && /[\\p{L}\\p{N},;:.!?]$/u.test(antes.textContent) && /^[\\p{L}\\p{N}]/u.test(t))
      p.push('palavra colada: …' + antes.textContent.slice(-12) + '⟨' + t.slice(0,12) + '⟩');
    if (!sigla && !folga(el, 'Right') && depois?.nodeType === 3 && /[\\p{L}\\p{N}]$/u.test(t) && /^[\\p{L}\\p{N}]/u.test(depois.textContent))
      p.push('palavra colada: ⟨' + t.slice(-12) + '⟩' + depois.textContent.slice(0,12) + '…');
  });

  // ── Contraste ─────────────────────────────────────────────
  // tokens.css escurece de propósito o azul e o laranja no tema claro, porque
  // os valores crus da marca dão 3,1:1 e 2,6:1 sobre branco. Esta checagem é o
  // que impede alguém de "corrigir" para o hex do guia e rebaixar a leitura —
  // e por isso ela precisa rodar nos dois temas.
  // Conversão de cor pelo próprio navegador, num canvas 1×1.
  //
  // Ler os números da string com regex parecia bastar e não bastava: o
  // .container usa color-mix(in oklab, ...), e o getComputedStyle devolve
  // "oklab(0.999 0.00004 0.00002 / 0.6)" — a regex lia 0.999 como se fosse o
  // canal R de 0 a 255, dava quase-preto, e o tema claro inteiro aparecia como
  // 30 falhas de contraste. Pintar e reler entrega sRGB para qualquer sintaxe
  // de cor que o navegador entenda (oklab, lab, color(), hsl…).
  const cnv = document.createElement('canvas');
  cnv.width = cnv.height = 1;
  const ctx = cnv.getContext('2d', { colorSpace: 'srgb', willReadFrequently: true });
  ctx.globalCompositeOperation = 'copy'; // substitui o pixel, não mistura
  const SENTINELA = '#010203';
  const rgb = (valor) => {
    const s = String(valor).trim();
    if (!s || s === 'transparent' || s === 'none') return null;

    // rgb()/rgba() é a esmagadora maioria dos casos e sai exato daqui. Passar
    // tudo pelo canvas parecia mais simples, mas a conversão de perfil de cor
    // varia ±1 por canal entre execuções: o mesmo rgb(106,114,133) voltava
    // 107,115,133 numa rodada e 106,114,133 na outra, e o contraste do rodapé
    // oscilava entre 4,12 e 4,19. O canvas fica só para o que a regex não sabe
    // ler — oklab, lab, color(), hsl.
    const m = s.match(/^rgba?\\(([^)]+)\\)$/);
    if (m) {
      const n = m[1].split(/[\\s,\\/]+/).filter(Boolean).map(Number);
      if (n.length >= 3 && n.slice(0, 3).every(Number.isFinite))
        return [n[0], n[1], n[2], n[3] === undefined ? 1 : n[3]];
    }

    ctx.fillStyle = SENTINELA;
    const invalida = ctx.fillStyle;
    ctx.fillStyle = s;
    if (ctx.fillStyle === invalida && s !== SENTINELA) return null; // não reconhecida
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };
  const canal = (c) => { c /= 255; return c <= 0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4) };
  const luz = ([r,g,b]) => 0.2126*canal(r) + 0.7152*canal(g) + 0.0722*canal(b);
  const razao = (a, b) => { const x = luz(a), y = luz(b);
    return (Math.max(x,y) + 0.05) / (Math.min(x,y) + 0.05) };
  const sobre = (frente, tras) => frente.slice(0,3).map((c, i) => c*frente[3] + tras[i]*(1-frente[3]));

  // Fundo efetivo: o .container é color-mix(... transparent), então a cor que o
  // olho vê só aparece compondo as camadas até achar uma opaca.
  function fundoDe(el) {
    const camadas = [];
    for (let n = el; n; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.backgroundImage !== 'none') return null; // gradiente/imagem: não dá para medir
      const c = rgb(cs.backgroundColor);
      if (!c || c[3] === 0) continue;
      camadas.push(c);
      if (c[3] >= 0.999) break;
    }
    let base = [255, 255, 255]; // o que sobra atrás de tudo é o branco do navegador
    for (let i = camadas.length - 1; i >= 0; i--) base = sobre(camadas[i], base);
    return base;
  }

  const temTexto = (el) => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
  document.querySelectorAll('body *').forEach(el => {
    if (!temTexto(el)) return;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity < 0.99) return;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;

    const cor = rgb(cs.color);
    const fundo = fundoDe(el);
    if (!cor || !fundo) return;
    const frente = cor[3] < 1 ? sobre(cor, fundo) : cor.slice(0,3);

    const px = parseFloat(cs.fontSize);
    const peso = parseInt(cs.fontWeight) || 400;
    const grande = px >= 24 || (px >= 18.66 && peso >= 700);
    const minimo = grande ? 3 : 4.5;
    const r_ = razao(frente, fundo);
    if (r_ < minimo)
      p.push('contraste ' + r_.toFixed(2) + ':1 (mín ' + minimo + ') em ' +
             el.tagName.toLowerCase() + '.' + (el.className + '').split(' ')[0] +
             ': "' + el.textContent.trim().slice(0, 24) + '"');
  });

  // ── Campos de formulário ──────────────────────────────────
  // Formulário É o produto aqui: campo sem rótulo associado é invisível para
  // leitor de tela e o clique no texto não foca o input.
  document.querySelectorAll('input, select, textarea').forEach(el => {
    if (el.type === 'hidden') return;
    const temLabel = (el.id && document.querySelector('label[for="' + CSS.escape(el.id) + '"]')) ||
      el.closest('label') || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
    if (!temLabel) p.push('campo sem rótulo: ' + el.tagName.toLowerCase() +
      '[name=' + (el.name || '?') + ']');
  });

  // ── Geometria ─────────────────────────────────────────────
  // Estourar a viewport só é bug se vazar para a página: dentro de um contêiner
  // que rola ou corta é o desenho pretendido, e sem esta ressalva toda tabela
  // do painel vira falso positivo no celular.
  const contido = (el) => {
    for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
      if (/auto|scroll|hidden/.test(getComputedStyle(a).overflowX)) return true;
    }
    return false;
  };

  document.querySelectorAll('body *').forEach(e => {
    const r = e.getBoundingClientRect();
    const cls = (e.className + '').split(' ')[0];
    if (r.width > 0 && (r.right > innerWidth + 2 || r.left < -2) && !contido(e))
      p.push('estoura a viewport: ' + e.tagName.toLowerCase() + '.' + cls);
    if (e.tagName === 'IMG' && !e.hasAttribute('alt')) p.push('img sem alt');
  });

  return [...new Set(p)];
})()`;

/**
 * As rotas saem do `dist/` do build, não de uma lista escrita à mão.
 *
 * Não há sitemap aqui (o público é `noindex` de propósito — é formulário de
 * cliente, não conteúdo). Mas o `dist/` serve igual: foi produzido pelo mesmo
 * build que gerou as páginas, então não tem como divergir. Lista fixa apodrece
 * — e como o servidor estático responde 404 com status 200 em alguns casos, a
 * auditoria passaria feliz tendo auditado a tela de erro.
 */
async function rotasPadrao() {
  if (!existsSync(DIST)) {
    throw new Error(
      `${DIST} não existe — rode \`bun run --cwd frontend build:${projeto}\` antes de auditar, ` +
        'ou passe as rotas na linha de comando.',
    );
  }

  const achadas = [];
  async function varrer(dir) {
    for (const item of await readdir(dir, { withFileTypes: true })) {
      const caminho = join(dir, item.name);
      if (item.isDirectory()) await varrer(caminho);
      else if (item.name.endsWith('.html')) achadas.push('/' + relative(DIST, caminho));
    }
  }
  await varrer(DIST);

  // `build.format: 'file'` mantém as URLs .html que já foram enviadas a
  // clientes; só o index vira raiz.
  return [...new Set(achadas.map((r) => (r === '/index.html' ? '/' : r)))].sort();
}

/**
 * Confere que quem atende em BASE é mesmo este frontend, antes de auditar.
 *
 * As rotas saem do `dist/` local, mas o navegador vai no servidor — e nada
 * amarra os dois. Se outro projeto tiver tomado a porta (4321 é a padrão do
 * Astro: qualquer site na máquina disputa ela), a auditoria mede a home alheia,
 * leva 404 nas outras rotas e ainda assim imprime "5 rota(s) sem problemas".
 * Aconteceu: o site institucional estava servindo em 4321 e a matriz inteira
 * saiu verde auditando o site errado.
 */
async function conferirServidor(rotas) {
  const faltando = [];
  for (const rota of rotas) {
    const r = await fetch(BASE + rota, { method: 'GET' }).catch(() => null);
    if (!r) throw new Error(`${BASE} não respondeu — o servidor está no ar? Veja Run no SKILL.md.`);
    if (!r.ok) faltando.push(`${rota} → ${r.status}`);
  }
  if (faltando.length) {
    throw new Error(
      `quem atende em ${BASE} não é o frontend "${projeto}":\n  ` +
        faltando.join('\n  ') +
        `\nOutro projeto tomou a porta? Confira com \`ss -ltnp\` ou aponte o alvo com SITE_URL.`,
    );
  }
}

// ---------------------------------------------------------------- comandos

if (!comando || comando === 'help') {
  console.log(`uso: bun .claude/skills/run-site/driver.mjs <comando>

  shot <rota> --out <arquivo> [--width 1440] [--height 900] [--theme dark|light] [--full]
  audit [rota…]                                          (sem rotas = todas do dist/)
  eval <rota> <expressão-js>

  --projeto public|admin  qual frontend (padrão public; define porta e dist/)
  --destravar             abre os portões pelo DOM, sem API nem credencial
  --token <t>             token de triagem real — precisa da API no ar
  --admin-key <chave>     faz login de verdade no painel — precisa da API no ar
  --scroll-to <seletor>   centraliza o elemento antes de fotografar
  --animate               NÃO congela animações

  SITE_URL    servidor alvo (padrão ${BASE})
  BROWSER_BIN caminho do Chromium (padrão: primeiro encontrado)`);
  process.exit(0);
}

const opcoes = {
  congelar: !ligada('animate'),
  destravar: ligada('destravar'),
  token: flag('token', null),
  adminKey: flag('admin-key', null),
  rolarAte: flag('scroll-to'),
};
// Com token válido ou login real o conteúdo aparece pelo caminho legítimo —
// a checagem de portão vazado não se aplica.
const comoAbriu = opcoes.adminKey
  ? 'login'
  : opcoes.token
    ? 'token'
    : opcoes.destravar
      ? 'destravado'
      : null;
const portoesAbertos = comoAbriu !== null;

const nav = await abrirNavegador();
let falhou = false;

try {
  const cli = await abrirAba(nav.porta);

  if (comando === 'shot') {
    const rota = posicionais[0] ?? '/';
    const saida = flag('out', '/tmp/shots/site.png');
    await preparar(cli, rota, opcoes);
    // `captureBeyondViewport` sozinho não estica a foto: o Chrome atual só sai
    // da dobra se receber um `clip` com o tamanho do documento. Sem isto o
    // --full devolvia exatamente os mesmos 900px de altura, em silêncio.
    const clip = ligada('full')
      ? await avaliar(
          cli,
          `(() => { const d = document.documentElement;
            return { x: 0, y: 0, width: d.scrollWidth, height: d.scrollHeight, scale: 1 } })()`,
        )
      : undefined;
    const { data } = await cli.send('Page.captureScreenshot', {
      format: 'png',
      ...(clip ? { clip, captureBeyondViewport: true } : {}),
    });
    await mkdir(dirname(saida), { recursive: true });
    await writeFile(saida, Buffer.from(data, 'base64'));
    console.log(`${saida}  (${rota} · ${projeto} · ${largura}px · ${tema})`);
  } else if (comando === 'audit') {
    const rotas = posicionais.length ? posicionais : await rotasPadrao();
    await conferirServidor(rotas);
    let total = 0;
    let auditadas = 0;
    for (const rota of rotas) {
      const final = await preparar(cli, rota, opcoes);
      if (final !== rota && !(rota === '/' && final === '/index.html')) {
        console.log(`  ↷ ${rota} redireciona para ${final} — pulando`);
        continue;
      }
      auditadas++;
      const achados = await avaliar(cli, auditoria(portoesAbertos));
      if (achados.length) {
        total += achados.length;
        console.log(`\n${rota}  (${largura}px · ${tema})`);
        achados.forEach((a) => console.log('  ✗ ' + a));
      }
    }
    const contexto = `${projeto} · ${largura}px · ${tema}${comoAbriu ? ' · ' + comoAbriu : ' · portões fechados'}`;
    if (total) {
      console.log(`\n${total} problema(s) em ${auditadas} rota(s).  (${contexto})`);
      falhou = true;
    } else if (!auditadas) {
      // Zero rota auditada não é sucesso — era o que saía ao pedir a tela de
      // atendimento direto pela URL: ela redireciona para `/` (a chave de admin
      // vive só em memória e não sobrevive à navegação), todas as rotas eram
      // puladas e o driver imprimia um ✓ tendo medido nada.
      console.log(`✗ nenhuma rota auditada — todas redirecionaram.  (${contexto})`);
      falhou = true;
    } else {
      console.log(`✓ ${auditadas} rota(s) sem problemas  (${contexto})`);
    }
  } else if (comando === 'eval') {
    const [rota, ...expr] = posicionais;
    await preparar(cli, rota ?? '/', opcoes);
    // Sem --esperar, uma expressão async vira `JSON.stringify(Promise)` e sai
    // como `{}` — silenciosamente inútil justamente quando você quer conferir
    // algo que só existe depois de um fetch.
    console.log(
      JSON.stringify(await avaliar(cli, expr.join(' '), { esperar: ligada('esperar') }), null, 2),
    );
  } else {
    console.error(`comando desconhecido: ${comando}`);
    falhou = true;
  }

  cli.fechar();
} catch (erro) {
  // Mensagem em vez de stack: o que importa aqui é "o servidor não está no ar"
  // ou "a chave está errada", não em que linha do driver isso apareceu.
  console.error('✗ ' + (erro?.message ?? erro));
  falhou = true;
} finally {
  await nav.encerrar();
}

process.exit(falhou ? 1 : 0);
