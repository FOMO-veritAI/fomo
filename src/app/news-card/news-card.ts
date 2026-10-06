import { Component, EventEmitter, Input, Output } from '@angular/core';
import { Article } from '../models';
import { AudioPlayerComponent } from '../audio-player/audio-player';
import { IconComponent } from '../icon/icon';

@Component({
  selector: 'app-news-card',
  standalone: true,
  imports: [AudioPlayerComponent, IconComponent],
  templateUrl: './news-card.html',
})
export class NewsCardComponent {
  @Input({ required: true }) article!: Article;
  @Input() liked = false;
  @Input() saved = false;
  @Input() rank = false;
  @Input() addedComments = 0;
  @Input() audioPlaying = false;
  @Output() openArticle = new EventEmitter<number>();
  @Output() openEvidence = new EventEmitter<number>();
  @Output() openComments = new EventEmitter<number>();
  @Output() viewReactions = new EventEmitter<number>();
  @Output() toggleLike = new EventEmitter<number>();
  @Output() toggleSave = new EventEmitter<number>();
  @Output() share = new EventEmitter<number>();
  @Output() toggleAudio = new EventEmitter<number>();
  @Output() audioInfo = new EventEmitter<number>();
  @Output() expertAudio = new EventEmitter<string>();
  @Output() more = new EventEmitter<number>();
}
