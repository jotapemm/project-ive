/**
 * A tela do IVE.
 *
 * Barra lateral + área de conversa, seguindo o desenho do Figma.
 *
 * A distinção que sustentava as duas colunas antigas continua viva, só
 * mudou de lugar: o que passa pelo MODELO entra pela caixa de texto; o que
 * NÃO passa (as ações diretas) são botões na barra. As respostas caem na
 * mesma conversa, mas marcadas — assim dá pra ver de onde cada coisa veio.
 *
 * Muita coisa aqui ainda é casca: Novo, Projetar, Desenvolver, Conversas,
 * Personalizar e voz não têm nada atrás. Estão marcadas com `title` e
 * desabilitadas em vez de fingirem que funcionam.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import { Abertura, LogoIVE } from "./Logo";
import * as tema from "./tema";
import * as voz from "./voz";
import { ModoVoz } from "./ModoVoz";

const JA_ABRIU = "ive-abriu";

type Mensagem =
  | { tipo: "voce"; texto: string }
  | { tipo: "ive"; texto: string; meta: api.Resultado }
  | { tipo: "direto"; ferramenta: string; dados: unknown }
  | { tipo: "erro"; texto: string };

export default function App() {
  const [saude, setSaude] = useState<api.Saude | null>(null);
  const [ferramentas, setFerramentas] = useState<api.Ferramenta[]>([]);
  const [erroInicial, setErroInicial] = useState<string | null>(null);
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [rodando, setRodando] = useState(false);
  const [motor, setMotor] = useState<string>("");

  const [vozPref, setVozPref] = useState(voz.carregar);
  const [vozes, setVozes] = useState<SpeechSynthesisVoice[]>([]);
  const [modoVoz, setModoVoz] = useState(false);

  // A lista de vozes chega assíncrona — ver o comentário em voz.ts.
  useEffect(() => {
    voz.vozes().then(setVozes);
    return () => voz.calar(); // não deixa fala órfã tocando após sair
  }, []);

  function trocarVoz(p: voz.Preferencias) {
    setVozPref(p);
    voz.guardar(p);
  }

  const falar = (texto: string) => voz.falar(texto, vozPref, vozes);

  const [abrindo, setAbrindo] = useState(
    () => sessionStorage.getItem(JA_ABRIU) !== "1",
  );

  const fecharAbertura = useCallback(() => {
    sessionStorage.setItem(JA_ABRIU, "1");
    setAbrindo(false);
  }, []);

  // Roda em paralelo com a animação de abertura.
  useEffect(() => {
    Promise.all([api.saude(), api.ferramentas()])
      .then(([s, f]) => {
        setSaude(s);
        setFerramentas(f);
        setMotor(s.motor);
      })
      .catch((e) => setErroInicial(e.message));
  }, []);

  async function enviar(texto: string) {
    if (!texto.trim() || rodando) return;
    setMensagens((m) => [...m, { tipo: "voce", texto }]);
    setRodando(true);
    try {
      const r = await api.executar(texto, motor || undefined);
      setMensagens((m) => [...m, { tipo: "ive", texto: r.resposta, meta: r }]);
      if (vozPref.auto) falar(r.resposta);
    } catch (e) {
      setMensagens((m) => [...m, { tipo: "erro", texto: (e as Error).message }]);
    } finally {
      setRodando(false);
    }
  }

  async function acaoDireta(nome: string, entrada: Record<string, unknown>) {
    try {
      const dados = await api.chamarFerramenta(nome, entrada);
      setMensagens((m) => [...m, { tipo: "direto", ferramenta: nome, dados }]);
    } catch (e) {
      setMensagens((m) => [...m, { tipo: "erro", texto: (e as Error).message }]);
    }
  }

  if (modoVoz) {
    return (
      <ModoVoz
        motor={motor}
        aoFalar={falar}
        aoSair={() => {
          voz.calar();
          setModoVoz(false);
        }}
      />
    );
  }

  return (
    <>
      {abrindo && <Abertura aoTerminar={fecharAbertura} />}
      {erroInicial ? (
        <TelaDeErro mensagem={erroInicial} />
      ) : (
        <div className="janela">
          <Barra
            saude={saude}
            ferramentas={ferramentas}
            aoAgir={acaoDireta}
            aoLimpar={() => {
              voz.calar();
              setMensagens([]);
            }}
            vozPref={vozPref}
            vozes={vozes}
            aoTrocarVoz={trocarVoz}
          />
          <Principal
            saude={saude}
            mensagens={mensagens}
            rodando={rodando}
            motor={motor}
            aoTrocarMotor={setMotor}
            aoEnviar={enviar}
            aoFalar={falar}
            aoEntrarNaVoz={() => setModoVoz(true)}
          />
        </div>
      )}
    </>
  );
}

/* --- barra lateral --------------------------------------------------- */

function Barra({
  saude,
  ferramentas,
  aoAgir,
  aoLimpar,
  vozPref,
  vozes,
  aoTrocarVoz,
}: {
  vozPref: voz.Preferencias;
  vozes: SpeechSynthesisVoice[];
  aoTrocarVoz: (p: voz.Preferencias) => void;
  saude: api.Saude | null;
  ferramentas: api.Ferramenta[];
  aoAgir: (nome: string, entrada: Record<string, unknown>) => void;
  aoLimpar: () => void;
}) {
  const [recolhida, setRecolhida] = useState(false);

  /*
   * A cascata é uma animação CSS, e animação CSS só toca quando o elemento
   * entra na tela. Trocar `key` remonta o bloco e faz ela tocar de novo —
   * é o jeito mais direto de "reproduzir" sem bibliotecar nada.
   */
  const [geracao, setGeracao] = useState(0);

  function alternar() {
    const vaiExpandir = recolhida;
    setRecolhida(!recolhida);
    if (vaiExpandir) setGeracao((g) => g + 1);
  }

  return (
    <aside className={`barra ${recolhida ? "recolhida" : ""}`}>
      <button
        className="hamburguer"
        onClick={alternar}
        aria-label={recolhida ? "Expandir a barra" : "Recolher a barra"}
      >
        ≡
      </button>

      <nav className="nav cascata" key={geracao}>
        <ItemNav passo={0} icone="+" rotulo="Novo" aoClicar={aoLimpar} />
        <ItemNav passo={1} icone="✳" rotulo="Projetar" pendente />
        <ItemNav passo={2} icone=">." rotulo="Desenvolver" pendente />
      </nav>

      <div className="rolagem cascata" key={`r${geracao}`}>
        <h2 className="secao">Conversas</h2>
        <p className="vazio">
          Nada por aqui — o IVE ainda não guarda conversa entre execuções.
        </p>

        <h2 className="secao">Ações diretas</h2>
        <p className="dica">Não passam pelo modelo. Instantâneas e sem custo.</p>
        <div className="acoes">
          <button onClick={() => aoAgir("listar_arquivos", {})}>
            Listar arquivos
          </button>
          <button
            onClick={() =>
              aoAgir("ler_planilha", { caminho: "clientes_agosto.xlsx" })
            }
          >
            Ler clientes_agosto
          </button>
          <button
            onClick={() =>
              aoAgir("inspecionar_coluna", {
                caminho: "clientes_agosto.xlsx",
                coluna: "E-mail",
              })
            }
          >
            Conferir coluna E-mail
          </button>
        </div>

        <h2 className="secao">Cardápio</h2>
        <p className="dica">
          O limite físico do agente: o que não está aqui não é alcançável.
        </p>
        <ul className="cardapio">
          {ferramentas.map((f) => (
            <li key={f.name} title={f.description}>
              <code>{f.name}</code>
              {f.escrita && <span className="escrita">ESCRITA</span>}
            </li>
          ))}
        </ul>
      </div>

      <footer className="rodape-barra">
        <Personalizar pref={vozPref} vozes={vozes} aoTrocarVoz={aoTrocarVoz} />
        <button className="usuario" disabled title="Ainda não existe">
          <span className="avatar" />
          <span>
            {saude ? saude.motor_descricao : "conectando…"}
          </span>
        </button>
      </footer>
    </aside>
  );
}

function ItemNav({
  icone,
  rotulo,
  passo,
  pendente,
  aoClicar,
}: {
  icone: string;
  rotulo: string;
  passo?: number;
  pendente?: boolean;
  aoClicar?: () => void;
}) {
  return (
    <button
      className="item-nav"
      style={{ "--passo": passo ?? 0 } as React.CSSProperties}
      onClick={aoClicar}
      disabled={pendente}
      title={pendente ? "Ainda não existe" : undefined}
    >
      <span className="icone">{icone}</span>
      <span>{rotulo}</span>
    </button>
  );
}

/* --- personalizar ---------------------------------------------------- */

/**
 * Você escolhe só o FUNDO. A cor do texto sai calculada pela luminância
 * dele (ver tema.ts), e painel, borda e tons apagados saem de color-mix
 * no CSS. Por isso não existe "tema claro" e "tema escuro" como código
 * separado — existe uma cor, e o resto obedece.
 *
 * Cada amostra mostra a letra na cor de texto que aquele fundo vai gerar,
 * então dá pra ver o contraste antes de clicar.
 */
function Personalizar({
  pref,
  vozes,
  aoTrocarVoz,
}: {
  pref: voz.Preferencias;
  vozes: SpeechSynthesisVoice[];
  aoTrocarVoz: (p: voz.Preferencias) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const [fundo, setFundo] = useState(tema.carregar);
  const ptBr = voz.vozesPtBr(vozes);

  function trocar(novo: string) {
    setFundo(novo);
    tema.aplicar(novo);
  }

  return (
    <>
      {aberto && (
        <div className="tema">
          <h3>Cor de fundo</h3>
          <div className="amostras">
            {tema.TEMAS.map((t) => (
              <button
                key={t.fundo}
                className={fundo === t.fundo ? "escolhido" : ""}
                style={{ background: t.fundo, color: tema.textoPara(t.fundo) }}
                onClick={() => trocar(t.fundo)}
                title={t.nome}
                aria-label={t.nome}
              >
                A
              </button>
            ))}
          </div>
          <label className="livre">
            <input
              type="color"
              value={fundo}
              onChange={(e) => trocar(e.target.value)}
            />
            <span>qualquer outra cor</span>
          </label>

          <h3 style={{ marginTop: 16 }}>Voz</h3>
          {!voz.suportado() || ptBr.length === 0 ? (
            <p className="dica" style={{ padding: 0 }}>
              Nenhuma voz em português instalada no Windows.
            </p>
          ) : (
            <>
              <label className="alternar">
                <input
                  type="checkbox"
                  checked={pref.auto}
                  onChange={(e) => aoTrocarVoz({ ...pref, auto: e.target.checked })}
                />
                <span>Falar as respostas automaticamente</span>
              </label>

              <select
                className="seletor-voz"
                value={pref.vozURI || ptBr[0]?.voiceURI}
                onChange={(e) => aoTrocarVoz({ ...pref, vozURI: e.target.value })}
              >
                {ptBr.map((v) => (
                  <option key={v.voiceURI} value={v.voiceURI}>
                    {v.name.replace(/^Microsoft\s+/, "").replace(/\s*-.*$/, "")}
                  </option>
                ))}
              </select>

              <label className="ritmo">
                <span>ritmo</span>
                <input
                  type="range"
                  min={0.7}
                  max={1.6}
                  step={0.05}
                  value={pref.ritmo}
                  onChange={(e) =>
                    aoTrocarVoz({ ...pref, ritmo: Number(e.target.value) })
                  }
                />
                <b>{pref.ritmo.toFixed(2)}×</b>
              </label>

              <button
                className="testar"
                onClick={() =>
                  voz.falar(
                    "Pronto. Sou o IVE, e é assim que eu soo.",
                    pref,
                    vozes,
                  )
                }
              >
                ▶ ouvir uma amostra
              </button>
            </>
          )}
        </div>
      )}
      <button
        className={`linha ${aberto ? "aberta" : ""}`}
        onClick={() => setAberto((a) => !a)}
        aria-expanded={aberto}
      >
        <span className="icone">◐</span>
        <span>Personalizar</span>
      </button>
    </>
  );
}

/* --- área principal -------------------------------------------------- */

function Principal({
  saude,
  mensagens,
  rodando,
  motor,
  aoTrocarMotor,
  aoEnviar,
  aoFalar,
  aoEntrarNaVoz,
}: {
  saude: api.Saude | null;
  mensagens: Mensagem[];
  rodando: boolean;
  motor: string;
  aoTrocarMotor: (m: string) => void;
  aoEnviar: (t: string) => void;
  aoFalar: (t: string) => void;
  aoEntrarNaVoz: () => void;
}) {
  const vazio = mensagens.length === 0;
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fim.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensagens.length, rodando]);

  const caixa = (
    <Caixa
      saude={saude}
      motor={motor}
      rodando={rodando}
      aoTrocarMotor={aoTrocarMotor}
      aoEnviar={aoEnviar}
      aoEntrarNaVoz={aoEntrarNaVoz}
    />
  );

  return (
    <main className={`principal ${vazio ? "hero" : ""}`}>
      {vazio ? (
        <div className="centro">
          <LogoIVE tamanho={64} modo="parada" />
          {caixa}
        </div>
      ) : (
        <>
          <div className="conversa">
            {mensagens.map((m, i) => (
              <Balao key={i} m={m} aoFalar={aoFalar} />
            ))}
            {rodando && <div className="pensando">pensando…</div>}
            <div ref={fim} />
          </div>
          <div className="ancora">{caixa}</div>
        </>
      )}
    </main>
  );
}

function Balao({ m, aoFalar }: { m: Mensagem; aoFalar: (t: string) => void }) {
  if (m.tipo === "voce")
    return <div className="balao voce">{m.texto}</div>;

  if (m.tipo === "erro")
    return <div className="balao erro">{m.texto}</div>;

  if (m.tipo === "direto")
    return (
      <div className="balao direto">
        <span className="etiqueta">direto · {m.ferramenta}</span>
        <pre>{JSON.stringify(m.dados, null, 2)}</pre>
      </div>
    );

  return (
    <div className="balao ive">
      <div className="texto">{m.texto}</div>
      <div className="rodape-balao">
        <span className="etiqueta">
          {m.meta.motor} · {m.meta.status} · {m.meta.passos} chamada(s) ·{" "}
          {m.meta.tokens_in}↑ {m.meta.tokens_out}↓
          {m.meta.cache_leitura > 0 && ` · ${m.meta.cache_leitura} do cache`}
        </span>
        {voz.suportado() && m.texto.trim() && (
          <button
            className="ouvir"
            onClick={() => aoFalar(m.texto)}
            title="Ouvir esta resposta"
            aria-label="Ouvir esta resposta"
          >
            ▶
          </button>
        )}
      </div>
    </div>
  );
}

function Caixa({
  saude,
  motor,
  rodando,
  aoTrocarMotor,
  aoEnviar,
  aoEntrarNaVoz,
}: {
  saude: api.Saude | null;
  motor: string;
  rodando: boolean;
  aoTrocarMotor: (m: string) => void;
  aoEnviar: (t: string) => void;
  aoEntrarNaVoz: () => void;
}) {
  const [texto, setTexto] = useState("");

  function mandar() {
    if (!texto.trim() || rodando) return;
    aoEnviar(texto);
    setTexto("");
  }

  return (
    <div className="caixa">
      <textarea
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            mandar();
          }
        }}
        placeholder="Como posso te ajudar?"
        rows={1}
        disabled={rodando}
      />
      <div className="pe">
        <span className="marca-pe" aria-hidden="true">
          &gt;.
        </span>
        <div className="controles">
          <select
            value={motor}
            onChange={(e) => aoTrocarMotor(e.target.value)}
            disabled={rodando || !saude}
            title="Qual cérebro responde"
          >
            {(saude?.motores ?? []).map((m) => (
              <option key={m} value={m}>
                {m === "local"
                  ? `local · ${saude?.modelo_local}`
                  : `nuvem · ${saude?.modelo}`}
              </option>
            ))}
          </select>
          {/* Troca a conversa de texto pela de voz. O push-to-talk mora
              lá dentro — aqui é só o interruptor. */}
          <button
            className="voz"
            onClick={aoEntrarNaVoz}
            title="Conversa por voz"
            aria-label="Conversa por voz"
          >
            ◎
          </button>
          <button className="enviar" onClick={mandar} disabled={rodando || !texto.trim()}>
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}


/* --- servidor fora do ar --------------------------------------------- */

function TelaDeErro({ mensagem }: { mensagem: string }) {
  return (
    <div className="erro-inicial">
      <div className="marca-centrada">
        <LogoIVE tamanho={44} modo="parada" />
      </div>
      <p>{mensagem}</p>
      <pre>
        cd C:\Users\UP\OneDrive\Desktop\.IVE{"\n"}
        .\.venv\Scripts\Activate.ps1{"\n"}
        uvicorn ive.servidor:app --host 127.0.0.1 --port 8010 --reload
      </pre>
    </div>
  );
}
