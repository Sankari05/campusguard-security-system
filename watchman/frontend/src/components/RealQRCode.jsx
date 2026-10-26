import React, { useEffect, useState } from 'react';
import QRCode from 'qrcode';

/**
 * RealQRCode Component
 * Generates an authentic, camera-scannable QR code using the 'qrcode' library.
 * Works seamlessly with mobile phone cameras, Google Lens, iOS Camera, and barcode scanners.
 */
export const RealQRCode = ({
  text,
  size = 220,
  darkColor = '#0F172A',
  lightColor = '#FFFFFF',
  className = '',
  style = {}
}) => {
  const [dataUrl, setDataUrl] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!text) {
      setDataUrl('');
      return;
    }

    let isMounted = true;
    QRCode.toDataURL(text, {
      width: size * 2, // 2x resolution for ultra-sharp scanning
      margin: 1,
      color: {
        dark: darkColor,
        light: lightColor
      },
      errorCorrectionLevel: 'M'
    })
      .then((url) => {
        if (isMounted) {
          setDataUrl(url);
          setError(null);
        }
      })
      .catch((err) => {
        console.error('RealQRCode generation error:', err);
        if (isMounted) setError(err.message || 'QR Generation failed');
      });

    return () => {
      isMounted = false;
    };
  }, [text, size, darkColor, lightColor]);

  if (error) {
    return (
      <div
        style={{
          width: size,
          height: size,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#FEF2F2',
          border: '1px solid #FECACA',
          borderRadius: '16px',
          padding: '1rem',
          color: '#DC2626',
          fontSize: '0.8rem',
          textAlign: 'center',
          ...style
        }}
        className={className}
      >
        <span>QR Error: {error}</span>
      </div>
    );
  }

  if (!dataUrl) {
    return (
      <div
        style={{
          width: size,
          height: size,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#F8FAFC',
          border: '1px solid #E2E8F0',
          borderRadius: '16px',
          color: '#64748B',
          fontSize: '0.85rem',
          fontWeight: 600,
          ...style
        }}
        className={className}
      >
        <span className="animate-pulse">Generating Scannable QR...</span>
      </div>
    );
  }

  return (
    <img
      src={dataUrl}
      alt={`QR Code: ${text}`}
      width={size}
      height={size}
      style={{
        display: 'block',
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: '12px',
        objectFit: 'contain',
        ...style
      }}
      className={className}
    />
  );
};
