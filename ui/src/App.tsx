/**
 * A tela do IVE.
 *
 * Barra lateral + área de conversa, seguindo o desenho do Figma.
 *
 * A barra mostra só o que é caminho: os três itens do menu, as conversas
 * e o rodapé. O cardápio de ferramentas e os botões de ação direta
 * moravam aqui e saíram — era tripa do motor exposta como decoração,
 * ocupando a barra inteira sem ninguém usar.
 *
 * Muita coisa aqui ainda é casca: Projetar, Desenvolver, Conversas e
 * Personalizar não têm nada atrás. Os dois primeiros ficaram CLICÁVEIS
 * de propósito — desabilitado não recebe :hover, e sem hover não há
 * animação nenhuma pra ver. O `title` é quem avisa que ainda não fazem
 * nada.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import { Abertura, LogoIVE } from "./Logo";
import * as tema from "./tema";
import * as voz from "./voz";
import { amostra } from "./frases";
import { ModoVoz } from "./ModoVoz";

const JA_ABRIU = "ive-abriu";

/**
 * A pergunta que veio da landing, em `?q=`.
 *
 * O site institucional (site/) tem uma caixa igual a esta. Quem escreve lá
 * é trazido pra cá com o texto junto, e reencontra a frase na mesma caixa —
 * a passagem não parece troca de site, parece a conversa continuando.
 *
 * Ela NÃO é enviada sozinha. Toda execução custa tokens e pode esbarrar no
 * servidor fora do ar; quem aperta enter é a pessoa.
 *
 * O parâmetro é apagado da barra de endereço depois de lido: sem isso, um
 * F5 ressuscitaria a pergunta antiga por cima do que o usuário já estivesse
 * escrevendo.
 */
function lerPergunta(): string {
  try {
    const q = new URLSearchParams(window.location.search).get("q");
    if (!q) return "";
    window.history.replaceState({}, "", window.location.pathname);
    return q.slice(0, 2000); // teto: ninguém cola um livro na barra de endereço
  } catch {
    return "";
  }
}

type Mensagem =
  | { tipo: "voce"; texto: string }
  | { tipo: "ive"; texto: string; meta: api.Resultado }
  | { tipo: "direto"; ferramenta: string; dados: unknown }
  | { tipo: "erro"; texto: string };

export default function App() {
  const [saude, setSaude] = useState<api.Saude | null>(null);
  const [erroInicial, setErroInicial] = useState<string | null>(null);
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [rodando, setRodando] = useState(false);
  const [motor, setMotor] = useState<string>("");

  const [vozPref, setVozPref] = useState(voz.carregar);
  const [modoVoz, setModoVoz] = useState(false);

  // Uma vez só, no primeiro render — a função já limpa a URL ao ler.
  const [daLanding] = useState(lerPergunta);

  // Não deixa fala órfã tocando se a tela sair.
  useEffect(() => () => voz.calar(), []);

  function trocarVoz(p: voz.Preferencias) {
    setVozPref(p);
    voz.guardar(p);
  }

  const falar = (texto: string) => voz.falar(texto, vozPref);

  const [abrindo, setAbrindo] = useState(
    () => sessionStorage.getItem(JA_ABRIU) !== "1",
  );

  const fecharAbertura = useCallback(() => {
    sessionStorage.setItem(JA_ABRIU, "1");
    setAbrindo(false);
  }, []);

  // Roda em paralelo com a animação de abertura.
  useEffect(() => {
    api
      .saude()
      .then((s) => {
        setSaude(s);
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
            aoLimpar={() => {
              voz.calar();
              setMensagens([]);
            }}
            vozPref={vozPref}
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
            daLanding={daLanding}
          />
        </div>
      )}
    </>
  );
}

/* --- barra lateral --------------------------------------------------- */

function Barra({
  saude,
  aoLimpar,
  vozPref,
  aoTrocarVoz,
}: {
  vozPref: voz.Preferencias;
  aoTrocarVoz: (p: voz.Preferencias) => void;
  saude: api.Saude | null;
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
        <ItemNav passo={0} arte="mais" rotulo="Novo" aoClicar={aoLimpar} />
        <ItemNav passo={1} arte="estrela" rotulo="Projetar" semDestino />
        <ItemNav passo={2} arte="codigo" rotulo="Desenvolver" semDestino />
      </nav>

      <div className="rolagem cascata" key={`r${geracao}`}>
        <h2 className="secao">Conversas</h2>
        <p className="vazio">
          Nada por aqui — o IVE ainda não guarda conversa entre execuções.
        </p>
      </div>

      <footer className="rodape-barra">
        <Personalizar
          saude={saude}
          pref={vozPref}
          aoTrocarVoz={aoTrocarVoz}
        />
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

/*
 * O ícone de cada item é um desenho, não um caractere solto: cada um tem
 * animação própria no hover, e animação precisa de peça pra mexer.
 *
 *   mais      vem pra frente e dá uma volta inteira
 *   estrela   o glifo some e vira um círculo de pontinhos
 *   codigo    o </> se apaga e se redigita, caractere por caractere
 *
 * Quem anima é o CSS. Aqui só existe a marcação que dá a ele o que mexer.
 */
type Arte = "mais" | "estrela" | "codigo";

const PONTOS = 22;
const RAIO = 8; // px — o tamanho da esferinha já aberta

/*
 * Ângulo áureo. Girar este tanto a cada ponto, com o raio crescendo em
 * raiz quadrada, espalha os pontos SEM alinhar em raios nem em anéis: é a
 * mesma matemática das sementes de girassol. Um ângulo redondo (45°, 60°)
 * empilharia tudo em braços de estrela; a raiz quadrada é o que mantém a
 * densidade igual do centro pra borda, em vez de amontoar no meio.
 */
const AUREO = 137.508;

function Icone({ arte }: { arte: Arte }) {
  if (arte === "estrela")
    return (
      <span className="icone icone-estrela" aria-hidden>
        <span className="glifo">✳</span>
        {/* Cada ponto carrega só o que é DELE: ângulo, raio, vez na fila
            e brilho. Tempo, curva e tamanho são iguais pra todos e moram
            no CSS. Os de dentro são mais claros que os de fora — é o que
            faz um punhado de pontos chapados parecer uma bolinha. */}
        {Array.from({ length: PONTOS }, (_, i) => {
          const r = RAIO * Math.sqrt((i + 0.5) / PONTOS);
          return (
            <i
              key={i}
              style={
                {
                  "--a": `${((i * AUREO) % 360).toFixed(1)}deg`,
                  "--r": `${r.toFixed(2)}px`,
                  "--i": i,
                  "--o": (1 - 0.55 * (r / RAIO)).toFixed(2),
                } as React.CSSProperties
              }
            />
          );
        })}
      </span>
    );

  if (arte === "codigo")
    return (
      <span className="icone icone-codigo" aria-hidden>
        <b>&lt;</b>
        <b>/</b>
        <b>&gt;</b>
      </span>
    );

  /*
   * O + é DESENHADO, e não o caractere "+" — glifo de fonte não fica no
   * centro da própria caixa, então girando ele o eixo cai fora do
   * cruzamento e o sinal bamboleia em vez de rodar.
   *
   * Repare que não há filho nenhum aqui: os dois traços são PINTADOS na
   * mesma caixa, pelo CSS. Já foram dois elementos, e o problema era que
   * cada um arredondava pra grade de pixels por conta própria — dava pra
   * um ganhar meio pixel de um lado e o outro do outro, e a cruz saía
   * desencontrada mesmo com a geometria exata. Pintados juntos, eles não
   * têm como discordar.
   */
  return <span className="icone icone-mais" aria-hidden />;
}

function ItemNav({
  arte,
  rotulo,
  passo,
  semDestino,
  aoClicar,
}: {
  arte: Arte;
  rotulo: string;
  passo?: number;
  semDestino?: boolean;
  aoClicar?: () => void;
}) {
  return (
    <button
      className="item-nav"
      style={{ "--passo": passo ?? 0 } as React.CSSProperties}
      onClick={aoClicar}
      title={semDestino ? "Ainda não existe" : undefined}
      /*
       * O preenchimento nasce ONDE O MOUSE ENTROU, não no meio do botão.
       * É o mesmo truque do <BotaoIVE> da landing: o JS só anota a
       * coordenada numa variável CSS, e quem cresce o círculo é a
       * transição. Sem isso o efeito é o mesmo pra qualquer entrada e
       * perde a graça — a mão do usuário é que dá a direção.
       */
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty("--x", `${e.clientX - r.left}px`);
        e.currentTarget.style.setProperty("--y", `${e.clientY - r.top}px`);
      }}
    >
      <Icone arte={arte} />
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
  saude,
  pref,
  aoTrocarVoz,
}: {
  saude: api.Saude | null;
  pref: voz.Preferencias;
  aoTrocarVoz: (p: voz.Preferencias) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const [fundo, setFundo] = useState(tema.carregar);

  const doPiper = saude?.fala_vozes ?? [];
  const temVoz = doPiper.length > 0;
  const vozEscolhida = pref.voz || saude?.fala_padrao || doPiper[0]?.nome || "";
  const vozAtual = doPiper.find((v) => v.nome === vozEscolhida);

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
          {!temVoz ? (
            <p className="dica" style={{ padding: 0 }}>
              Nenhuma voz baixada. Rode, na pasta do projeto:
              <br />
              <code>python -m piper.download_voices pt_BR-faber-medium
              --download-dir vozes</code>
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

              {/* Lista rasa: há uma voz de cada gênero, e agrupar duas
                  opções por motor era mais moldura que conteúdo. O aviso
                  de lentidão continua existindo — virou a linha abaixo,
                  que fala só da voz escolhida. */}
              <select
                className="seletor-voz"
                value={pref.voz || saude?.fala_padrao || doPiper[0]?.nome}
                onChange={(e) => aoTrocarVoz({ ...pref, voz: e.target.value })}
              >
                {doPiper.map((v) => (
                  <option key={v.nome} value={v.nome}>
                    {v.genero === "f" ? "Feminina" : "Masculina"}
                  </option>
                ))}
              </select>

              {vozAtual && !vozAtual.rapida && (
                <p className="dica" style={{ padding: "6px 0 0" }}>
                  Esta voz leva alguns segundos por frase. Boa para frase
                  curta.
                </p>
              )}

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
                onClick={() => voz.falar(amostra(vozEscolhida), pref)}
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
  daLanding,
}: {
  saude: api.Saude | null;
  mensagens: Mensagem[];
  rodando: boolean;
  motor: string;
  aoTrocarMotor: (m: string) => void;
  aoEnviar: (t: string) => void;
  aoFalar: (t: string) => void;
  aoEntrarNaVoz: () => void;
  daLanding: string;
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
      inicial={daLanding}
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
        {m.texto.trim() && (
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
  inicial = "",
}: {
  saude: api.Saude | null;
  motor: string;
  rodando: boolean;
  aoTrocarMotor: (m: string) => void;
  aoEnviar: (t: string) => void;
  aoEntrarNaVoz: () => void;
  /** Pergunta trazida da landing por `?q=`. Vazia no uso normal. */
  inicial?: string;
}) {
  const [texto, setTexto] = useState(inicial);
  const area = useRef<HTMLTextAreaElement>(null);

  /*
   * Chegou da landing: põe o cursor no fim do texto, pronto pra continuar
   * escrevendo ou só apertar enter. Sem o `setSelectionRange` o Chrome
   * deixa o cursor no começo da frase, o que é o oposto do esperado.
   */
  useEffect(() => {
    if (!inicial) return;
    const el = area.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(inicial.length, inicial.length);
  }, [inicial]);

  function mandar() {
    if (!texto.trim() || rodando) return;
    aoEnviar(texto);
    setTexto("");
  }

  return (
    <div className="caixa">
      <textarea
        ref={area}
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
