import { Component, EventEmitter, Input, Output } from '@angular/core';
import { AUDIO } from '../data';
import { Article } from '../models';
import { IconComponent } from '../icon/icon';

@Component({
  selector: 'app-audio-player',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './audio-player.html',
})
export class AudioPlayerComponent {
  @Input({ required: true }) article!: Article;
  @Input() compact = false;
  @Input() playing = false;
  @Output() togglePlay = new EventEmitter<number>();
  @Output() showInfo = new EventEmitter<number>();
  @Output() playExpert = new EventEmitter<string>();

  get audio() {
    return AUDIO[this.article.id];
  }

  readonly bars = Array.from({ length: 19 });
}
