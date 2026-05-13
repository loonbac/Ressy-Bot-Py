import './WelcomeBannerPreview.css';
import './animations.css';

interface Props {
  backgroundUrl: string;
  avatarUrl?: string;
  username: string;
  accentHex: string;
}

const FALLBACK_BG =
  'linear-gradient(135deg, #1a1c1a 0%, #2f312f 100%)';

export default function WelcomeBannerPreview({
  backgroundUrl,
  avatarUrl,
  username,
  accentHex,
}: Props) {
  return (
    <div
      key={`${backgroundUrl}|${accentHex}`}
      className="welcome-banner-preview animate-welcome-banner-reveal"
      style={
        backgroundUrl
          ? { backgroundImage: `url(${backgroundUrl})` }
          : { background: FALLBACK_BG }
      }
    >
      <div className="welcome-banner-preview__shade" />
      <div className="welcome-banner-preview__content">
        <div
          className="welcome-banner-preview__avatar-ring"
          style={{ backgroundColor: accentHex }}
        >
          <div className="welcome-banner-preview__avatar">
            {avatarUrl ? (
              <img src={avatarUrl} alt={username} />
            ) : (
              <span className="material-symbols-outlined">person</span>
            )}
          </div>
        </div>
        <div className="welcome-banner-preview__text">
          <p className="welcome-banner-preview__title">BIENVENIDO/A</p>
          <p
            className="welcome-banner-preview__name"
            style={{ color: accentHex }}
          >
            {username}
          </p>
        </div>
      </div>
    </div>
  );
}
