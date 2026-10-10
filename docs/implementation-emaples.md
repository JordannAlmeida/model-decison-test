# Implementacao de cases de exemplo do modelo de decisao

## Listagem

1. Roteamento Dinâmico por Complexidade da Entrada (LLM Routing)
Cenário: Nem toda pergunta do usuário precisa ser respondida por um modelo topo de linha e caro (como Claude Opus ou GPT-4o). Perguntas simples podem ser resolvidas por modelos muito mais baratos e rápidos (como Haiku ou Flash).
Uso do Jev: O Jev analisa o texto enviado pelo usuário e avalia a sua complexidade ou intenção.
Decisão: Se o Jev retornar "Simples", o sistema envia para um modelo leve/barato. Se retornar "Complexa/Raciocínio Avançado", o sistema encaminha para o modelo robusto.
Resultado: Redução drástica dos custos de infraestrutura de IA sem perder qualidade nas respostas complexas.
2. Avaliação da Qualidade da Resposta de Agentes (LLM-as-a-Judge)
Cenário: Em sistemas de múltiplos agentes de IA, é preciso garantir que a resposta gerada por um agente realmente resolveu o problema antes de exibi-la ao usuário final.
Uso do Jev: O Jev recebe a pergunta do usuário e a resposta gerada pelo agente, fornecendo um Score ou classificação.
Exemplo: Avalia em uma escala a clareza, a precisão e a presença de possíveis alucinações. Se a nota for abaixo do limiar estipulado, a resposta é rejeitada e enviada para ajuste ou para um operador humano.
3. Re-ordenação de Dados Recuperados em RAG (Reranking de Busca)
Cenário: Em sistemas RAG (Retrieval-Augmented Generation), a busca vetorial pode retornar 10 ou 20 trechos de documentos, mas enviar todos para a IA gerativa polui o contexto e aumenta o custo.
Uso do Jev: O Jev atua como um Reranker de altíssima velocidade. Ele atribui uma nota de relevância para cada trecho recuperado em relação à pergunta do usuário.
Resultado: O sistema seleciona apenas os 3 trechos com as maiores pontuações calculadas pelo Jev para compor o prompt final.
4. Classificação e Triagem de Tipos de E-mail
Cenário: Caixas de entrada corporativas ou de sistemas de atendimento recebem centenas de e-mails heterogêneos todos os dias.
Uso do Jev: O Jev lê o assunto e o corpo do e-mail e aplica uma classificação de múltipla escolha (Choice).
Exemplo de categorias: Fatura/Comprovante, Solicitação de Suporte, Proposta Comercial, Spam/Descarte ou Cancelamento.
Ação subsequente: E-mails de comprovante acionam a leitura automática de anexos; solicitações de suporte vão para o sistema de tickets; solicitações de cancelamento acionam o setor de retenção.
5. Detecção de Intent de Cancelamento / Risco de Churn
Uso do Jev: Avalia mensagens de usuários em chats ou chamados para dar uma nota de risco de cancelamento (Churn Score), alertando a equipe de Sucesso do Cliente imediatamente quando identificar alto risco.
6. Validação de Formulários e Entradas de Usuários
Uso do Jev: Analisa campos de texto livre digitados por usuários em sistemas (como justificativas de reembolso ou descrições de sinistro em seguradoras) para classificar se a informação fornecida é coerente e suficiente antes de permitir o envio do formulário.
7. Triagem e Roteamento de Suporte ao Cliente
O que faz: Lê mensagens de e-mail ou tickets de atendimento e decide instantaneamente a categoria e prioridade.
Exemplo: Classifica o ticket como Técnico, Financeiro ou Vendas, e o direciona automaticamente para a fila do setor correto.
8. Guardrails e Moderação ("Fiscal de IAs")
O que faz: Valida respostas geradas por chatbots antes que sejam enviadas ao usuário.
Exemplo: Verifica se a resposta gerada por uma IA gerativa descumpriu regras da empresa (como prometer um desconto indevido) e bloqueia a mensagem se necessário.
9. Qualificação e Pontuação de Leads (Lead Scoring)
O que faz: Analisa informações de contatos no CRM para categorizar o nível de prontidão para compra.
Exemplo: Avalia o perfil de um cliente e decide se ele está "Pronto para fechamento", "Necessita nutrição" ou "Lead frio".
10. Análise de Sentimento e Feedback em Massa
O que faz: Processa grandes volumes de avaliações, comentários ou respostas de pesquisas e atribui pontuações numéricas.
Exemplo: Atribui uma nota de 1 a 5 para o nível de insatisfação de cada avaliação recebida, permitindo filtrar e priorizar os clientes mais insatisfeitos.
11. Tomada de Decisão em Jogos (Lógica de NPCs)
O que faz: Serve como o motor de decisão rápida para o comportamento de personagens não-jogáveis.
Exemplo: Em um jogo de ação, analisa o estado da partida em tempo real e decide a próxima ação do NPC entre opções predefinidas (Atacar, Recuar, Buscar cobertura ou Curar-se).
12. Triagem Inicial de Pré-Atendimento Especializado
O que faz: Identifica a categoria específica do problema de um cliente no primeiro contato para disparar o formulário ou fluxo correto.
Exemplo: Em um escritório de advocacia ou clínica, classifica a mensagem do paciente/cliente na área correta antes de iniciar a coleta de dados subsequente.

## Regra de implementacao

Deve implementar na pasta examples um arquivo .py para cada caso de uso. Pode ter multiplas rodadas quando aplicavel ou multiplos exemplos sem conexao, o que fizer mais sentido de acordo com o contexto de cada exemplo. Considere apenas exemplos ludicos, entao pode partir de cenarios pre-existentes, como por exemplo o caso de reranking do rag, pode realizar um mock da parte recuperada e so fazer a reodernacao, sem ter que implementar todo um rag. Esse conceito vale para todos os exemplos. Todos os exemplos devem ser em portugues (pt-br).

Para cada exemplo, deve ser gerado um ou mais cenarios bonus, tentando estressar o limite do modelo de decisao, seja com um state (contexto) grande, ou com perguntas dificeis de classificar, ou outro cenario que julgar que podemos alcancar o limite de classificacao do modelo.

Os exemplos devem ser desacoplados do modelo de decisao e entre si, ou seja, utilizar via injecao de dependencia a saida do factory de modelos de decisao. Quem cuida de toda a execucao e o main.py

Alem disso crie de forma isolada uma classe de report. Ela deve gerar um html dinamico com de report com cada caso, o trace completo de entradas e saidas por exemplo e os resultados do teste de fogo (cenario bonus). Salve o resultado na pasta `/output`. Nao crie acoplamento dos exemplos e a geracao de report, a execucao dos exemplos deve ser independente da geracao do report. 

Faca cada implementacao por etapas. Use a modelagem do nosso scheme.py. Regras de uso de cada parte podemos encontrar nas docs do Jev (o mesmo vale para o Laya):
- https://docs.typesafe.ai/concepts/system-one
- https://docs.typesafe.ai/concepts/state
- https://docs.typesafe.ai/primitives/choice
- https://docs.typesafe.ai/primitives/score
- https://docs.typesafe.ai/primitives/noul
- https://docs.typesafe.ai/primitives/advanced

## Duvidas

Se necessario me pergunte sobre qualquer duvida antes de seguir