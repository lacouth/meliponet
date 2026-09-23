/* Desenha os tres graficos da pagina de uma colmeia.
 *
 * Os dados nao estao aqui: o servidor os escreve na pagina, num bloco
 * <script type="application/json" id="dados-do-grafico">, e este arquivo so os le.
 * Assim o mesmo arquivo serve para qualquer colmeia e qualquer janela.
 *
 * Roda de novo a cada 60 s, quando o HTMX troca o fragmento do painel.
 */
(function () {
  const bloco = document.getElementById("dados-do-grafico");
  if (!bloco) return;
  const dados = JSON.parse(bloco.textContent);

  // Graficos anteriores precisam ser destruidos: o HTMX troca o HTML, mas as
  // instancias do Chart.js sobreviveriam presas aos canvas antigos -- e a pagina
  // vazaria um grafico por minuto.
  window.graficosDaColmeia = window.graficosDaColmeia || [];
  window.graficosDaColmeia.forEach(function (grafico) { grafico.destroy(); });
  window.graficosDaColmeia = [];

  const opcoes = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    elements: { point: { radius: 0 }, line: { borderWidth: 2, tension: 0.25 } },
    scales: {
      x: { ticks: { maxTicksLimit: 8, color: "#7a7266" }, grid: { display: false } },
      y: { ticks: { color: "#7a7266" }, grid: { color: "#eee7da" } }
    },
    plugins: { legend: { labels: { boxWidth: 12, color: "#2b2721" } } }
  };

  function desenhar(id, linhas) {
    const canvas = document.getElementById(id);
    if (!canvas) return;
    // `spanGaps` fica desligado de proposito: uma lacuna na serie e informacao, e o
    // grafico precisa mostrar o buraco em vez de ligar os vizinhos por cima dele.
    window.graficosDaColmeia.push(new Chart(canvas, {
      type: "line",
      data: { labels: dados.rotulos, datasets: linhas },
      options: opcoes
    }));
  }

  // As chaves de `dados.series` sao os nomes do contrato (temp_in_c...), iguais aos
  // da mensagem que o no envia.
  desenhar("grafico-temp", [
    { label: "Interna (°C)", data: dados.series.temp_in_c, borderColor: "#c8791a" },
    { label: "Externa (°C)", data: dados.series.temp_out_c, borderColor: "#4f7fa8" },
    { label: "Δ interna − externa (°C)", data: dados.diferencial_termico,
      borderColor: "#9a8fb8", borderDash: [5, 4] }
  ]);

  desenhar("grafico-peso", [
    { label: "Peso (kg)", data: dados.series.weight_kg, borderColor: "#6a8f4f",
      fill: true, backgroundColor: "rgba(106,143,79,0.10)" }
  ]);

  desenhar("grafico-umidade", [
    { label: "Interna (%)", data: dados.series.rh_in_pct, borderColor: "#c8791a" },
    { label: "Externa (%)", data: dados.series.rh_out_pct, borderColor: "#4f7fa8" }
  ]);
})();
