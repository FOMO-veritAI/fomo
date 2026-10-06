import { Component, Input } from '@angular/core';

// Assinatura tipográfica da VeritAI: "Verit" serifada itálica + "AI" grotesca pesada.
// Para o logo completo (com moldura), use a imagem brand/web/veritai-logo.png.
@Component({
  selector: 'app-veritai-mark',
  standalone: true,
  template: `<span class="veritai-mark" [class.veritai-mark-lg]="size === 'lg'" role="img" [attr.aria-label]="caption ? 'VeritAI (in FOMO)' : 'VeritAI'"><span class="verit" aria-hidden="true">Verit</span><span class="verit-ai" aria-hidden="true">AI</span>@if (caption) {<span class="verit-caption" aria-hidden="true">(IN FOMO)</span>}</span>`,
})
export class VeritaiMarkComponent {
  @Input() size: 'sm' | 'lg' = 'sm';
  @Input() caption = false;
}
