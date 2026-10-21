# Pendências e conflitos documentais

Visão derivada de `conflicts.json`; nenhuma interpretação foi aprovada automaticamente.

## source-originals-missing — PDFs originais ausentes

Tipo: `missing_source` · Gravidade: `high` · Estado: `pending_validation`

- Fonte `folha-ponto`, versão `snapshot-local-v1`, página 1, seção/registro `2.` (`fp-deadline`).
- Fonte `vt-segunda-via`, versão `snapshot-local-v1`, página 2, seção/registro `89` (`vt-89`).

- Somente renderizações e extrações preexistentes estão disponíveis.
- Não é possível calcular o hash dos PDFs originais nem comprovar seus nomes/versões.

Próxima ação: Obter os originais autorizados, conferir integridade e revisar todas as evidências derivadas.

Revisor/data institucional: não informados.

## vt-3854-fee — Rápido D'Oeste: unidades de taxa não conciliadas

Tipo: `potential_conflict` · Gravidade: `high` · Estado: `pending_validation`

- Fonte `vt-segunda-via`, versão `snapshot-local-v1`, página 1, seção/registro `3854` (`vt-3854`).

- Coluna Taxa: 6 tarifas.
- Procedimento: taxa de 21,30, sem comprovação de equivalência entre unidades.

Próxima ação: Confirmar taxa e unidade com a área/operadora; preservar ambos os registros sem converter tarifas em reais.

Revisor/data institucional: não informados.

## vt-503-requester — SOU Diadema: solicitante

Tipo: `potential_conflict` · Gravidade: `high` · Estado: `pending_validation`

- Fonte `vt-segunda-via`, versão `snapshot-local-v1`, página 2, seção/registro `503` (`vt-503`).

- Coluna Quem solicita: Jovem.
- Procedimento: qualquer pessoa pode solicitar; retirada também permite outra pessoa com documento do titular.

Próxima ação: Confirmar regras de solicitação, representação e retirada; não escolher uma interpretação silenciosamente.

Revisor/data institucional: não informados.

## fp-send-vs-portal — Folha Ponto / Conecta Jovem: canais de envio

Tipo: `potential_conflict` · Gravidade: `high` · Estado: `pending_validation`

- Fonte `folha-ponto`, versão `snapshot-local-v1`, página 2, seção/registro `6.` (`fp-send`).
- Fonte `operational-services`, versão `operational-snapshot-v1`, página não paginada, seção/registro `services/send_timesheet` (`op-send`).

- PDF, seção 6, página 2: e-mail/WhatsApp do RH Jovem.
- Orientação operacional /services/send_timesheet: Conecta Jovem.
- Não há documento de substituição ou revogação dos canais anteriores.

Próxima ação: Pedir confirmação institucional da convivência ou substituição de canais; não declarar nenhum canal revogado.

Revisor/data institucional: não informados.

## vt-15779-address — Bem Santana: endereço ausente e referência sem protocolo

Tipo: `missing_information` · Gravidade: `medium` · Estado: `pending_validation`

- Fonte `vt-segunda-via`, versão `snapshot-local-v1`, página 1, seção/registro `15779` (`vt-15779`).

- O procedimento remete ao endereço mencionado abaixo, mas a linha não traz o endereço.
- A referência www.bemsantana.com.br não contém protocolo; acessibilidade não testada.

Próxima ação: Obter endereço completo e URL confirmada, sem completar ou consultar serviços externos nesta sprint.

Revisor/data institucional: não informados.

## vt-9156-channel — TOP: autoatendimento e WhatsApp sem destino

Tipo: `missing_information` · Gravidade: `medium` · Estado: `pending_validation`

- Fonte `vt-segunda-via`, versão `snapshot-local-v1`, página 2, seção/registro `9156` (`vt-9156`).

- Procedimento menciona chat/autoatendimento e WhatsApp, sem URL ou número.

Próxima ação: Confirmar canais oficiais e vigência da taxa; não inferir URL ou telefone.

Revisor/data institucional: não informados.

## vt-155-phone — Transurc Campinas: 0800 incompleto

Tipo: `missing_information` · Gravidade: `medium` · Estado: `pending_validation`

- Fonte `vt-segunda-via`, versão `snapshot-local-v1`, página 2, seção/registro `155` (`vt-155`).

- Procedimento menciona 0800 sem número completo.
- Taxa varia conforme a via; a faixa agregada não é uma taxa única.

Próxima ação: Solicitar número completo e confirmação dos valores por via; não completar número nem uniformizar a faixa.

Revisor/data institucional: não informados.

## instructor-missing-contact — Diretório: contato não informado

Tipo: `missing_information` · Gravidade: `medium` · Estado: `pending_validation`

- Fonte `instructor-directory`, versão `operational-snapshot-v1`, página não paginada, seção/registro `instructors/instructor-11` (`instructor-missing`).

- 16 registros no diretório local; 15 possuem e-mail e um tem email:null. Nenhum nome/e-mail pessoal foi republicado.

Próxima ação: Validar diretório restrito e confirmar contato pendente; não deduzir e-mail pelo nome.

Revisor/data institucional: não informados.

## operational-validation — Serviços e contatos operacionais pendentes

Tipo: `missing_approval` · Gravidade: `high` · Estado: `pending_validation`

- Fonte `operational-services`, versão `operational-snapshot-v1`, página não paginada, seção/registro `services/calendar` (`op-calendar`).
- Fonte `operational-services`, versão `operational-snapshot-v1`, página não paginada, seção/registro `services/course_certificate` (`op-course-certificate`).
- Fonte `education-contacts`, versão `operational-snapshot-v1`, página não paginada, seção/registro `education` (`education-inventory`).

- validation_status=pending e enabled=true no arquivo de configuração.
- Habilitação técnica não representa aprovação ou vigência institucional.

Próxima ação: Validar serviços, permissões, contatos e responsáveis; manter uso corporativo bloqueado na política de avaliação.

Revisor/data institucional: não informados.
