// Ícones e textos únicos para resultados e relações da VeritAI, sem cor.
// A mesma ideia usa o mesmo ícone em qualquer lugar: "contradiz" é sempre ≠, "apoia" é sempre ✓.
export const RESULTADO: Record<string, { icon: string; text: string }> = {
  SUPPORTED: { icon: '✓', text: 'As evidências apoiam' },
  REFUTED: { icon: '≠', text: 'As evidências contradizem' },
  NOT_ENOUGH_EVIDENCE: { icon: '?', text: 'Evidências insuficientes' },
  CONFLICTING_EVIDENCE: { icon: '⇄', text: 'Conclusões diferentes' },
};

// Resultado ausente ou desconhecido (ex.: análise ainda não feita).
export const SEM_RESULTADO = { icon: '·', text: 'Sem resultado' };

// Relação de uma evidência com a afirmação (contrato: apoia | contradiz | neutro; legado: entailment etc.).
export const RELACAO: Record<string, { icon: string; text: string }> = {
  apoia: { icon: '✓', text: 'Apoia' },
  contradiz: { icon: '≠', text: 'Contradiz' },
  neutro: { icon: '○', text: 'Neutra' },
  entailment: { icon: '✓', text: 'Apoia' },
  contradiction: { icon: '≠', text: 'Contradiz' },
  neutral: { icon: '○', text: 'Neutra' },
};
