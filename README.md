# WebGIS Pimenta Dedo-de-Moça em São Paulo

WebGIS municipal da GeoTerra Sensoriamento dedicado à cadeia produtiva da pimenta dedo-de-moça em São Paulo, seguindo a mesma metodologia visual do WebGIS do limão.

## Conteúdo

- mapa coroplético dos 645 municípios paulistas;
- panorama municipal de pimentas do Censo Agropecuário 2017;
- registro específico de pimenta dedo-de-moça de Santa Adélia em 2026;
- indicadores, ranking, histórico, mercado e fontes;
- cotações de atacado da CEAGESP e da CEASA Campinas;
- histórico acumulado das cotações para sínteses mensais, semestrais e anuais;
- volume mensal, sazonalidade e principais municípios remetentes informados pela CEAGESP;
- atualização automática dos preços às segundas, quartas e sextas-feiras;
- unidade piloto Pimentas Mariotto em Santa Adélia;
- exportação dos dados exibidos em CSV.

Os dados municipais de 2017 vêm da tabela 6953 do IBGE/SIDRA, categoria “Pimenta”, que reúne variedades de pimenta e não somente dedo-de-moça. Os dados de 2026 são registros próprios da Pimentas Mariotto. Valores sob sigilo estatístico ou sem informação permanecem sem valor numérico. A malha municipal é obtida do IBGE e o mapa-base utiliza OpenStreetMap.

As cotações e o histórico acumulado ficam em `prices.json`. A rotina `scripts/update_prices.py`, executada pelo GitHub Actions, consulta a pimenta dedo-de-moça na CEAGESP e o boletim mais recente da CEASA Campinas. Cada coleta válida é incorporada à série histórica; se uma fonte falhar, o último valor válido é preservado.

Os dados de mercado não são apresentados como produção agrícola. O volume da CEAGESP representa entrada/comercialização no entreposto, enquanto os registros municipais do mapa vêm do Censo Agropecuário ou da unidade piloto identificada.

Desenvolvido por Geovane Mariotto · GeoTerra Sensoriamento.
