import React from 'react';

interface CompanyLogoProps {
  symbol: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  showText?: boolean;
}

export const CompanyLogo: React.FC<CompanyLogoProps> = ({
  symbol,
  size = 'md',
  className = '',
  showText = false,
}) => {
  const sizeClasses = {
    sm: 'w-6 h-6 text-[10px]',
    md: 'w-8 h-8 text-xs',
    lg: 'w-11 h-11 text-sm',
    xl: 'w-14 h-14 text-base',
  }[size];

  switch (symbol.toUpperCase()) {
    case 'FPT':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-white border border-[#E1E7EF] shadow-xs p-1 ${sizeClasses} ${className}`}>
          {/* FPT Iconic Tri-Color Emblem SVG */}
          <svg viewBox="0 0 100 100" className="w-full h-full">
            {/* Orange curve */}
            <path d="M18 55 C18 35, 30 20, 50 18 C35 30, 32 45, 32 60 Z" fill="#F37021" />
            {/* Green curve */}
            <path d="M52 18 C72 20, 84 35, 84 55 C70 42, 58 35, 48 30 Z" fill="#5CB85C" />
            {/* Blue curve */}
            <path d="M30 65 C45 82, 65 82, 80 65 C68 72, 45 74, 30 65 Z" fill="#0066B3" />
            {/* FPT Text */}
            <text x="50" y="55" textAnchor="middle" dominantBaseline="middle" fill="#0066B3" fontWeight="900" fontSize="28" fontFamily="sans-serif">
              FPT
            </text>
          </svg>
        </div>
      );

    case 'VNM':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-[#003399] text-white font-black tracking-tight shadow-xs border border-[#002266] p-1 ${sizeClasses} ${className}`}>
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <rect width="100" height="100" rx="18" fill="#003399" />
            <path d="M20 70 L38 28 L50 28 L35 70 Z" fill="#FFFFFF" />
            <path d="M48 70 L65 35 L70 35 L58 70 Z" fill="#FBBF24" />
            <text x="50" y="86" textAnchor="middle" fill="#FFFFFF" fontWeight="900" fontSize="18" letterSpacing="1">
              VNM
            </text>
          </svg>
        </div>
      );

    case 'HPG':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-[#004B87] text-white shadow-xs p-1 border border-[#003B6D] ${sizeClasses} ${className}`}>
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <rect width="100" height="100" rx="18" fill="#004B87" />
            {/* Hòa Phát 3 Blue Steel geometric chevrons */}
            <polygon points="50,20 78,70 65,70 50,42 35,70 22,70" fill="#FFFFFF" />
            <polygon points="50,42 62,64 38,64" fill="#38BDF8" />
            <text x="50" y="88" textAnchor="middle" fill="#FFFFFF" fontWeight="900" fontSize="16">
              HÒA PHÁT
            </text>
          </svg>
        </div>
      );

    case 'MWG':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-[#FED000] shadow-xs p-1 border border-[#E5BC00] ${sizeClasses} ${className}`}>
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <rect width="100" height="100" rx="18" fill="#FED000" />
            <circle cx="50" cy="50" r="32" fill="#000000" />
            <circle cx="50" cy="38" r="8" fill="#FED000" />
            <path d="M42 50 C42 46, 58 46, 58 50 L56 68 L44 68 Z" fill="#FED000" />
            <path d="M34 52 L42 58 L40 64 L30 56 Z" fill="#FED000" />
            <path d="M66 52 L58 58 L60 64 L70 56 Z" fill="#FED000" />
          </svg>
        </div>
      );

    case 'VCB':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-[#00693E] shadow-xs p-1 border border-[#005230] ${sizeClasses} ${className}`}>
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <rect width="100" height="100" rx="18" fill="#00693E" />
            {/* Green continuous ribbon/diamond */}
            <path d="M50 20 L78 50 L50 80 L22 50 Z" fill="none" stroke="#FFFFFF" strokeWidth="8" />
            <circle cx="50" cy="50" r="10" fill="#78C257" />
          </svg>
        </div>
      );

    case 'SSI':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-white border border-[#E1E7EF] shadow-xs p-1 ${sizeClasses} ${className}`}>
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <rect width="100" height="100" rx="18" fill="#FFFFFF" />
            <path d="M25 35 C25 25, 45 25, 50 35 C55 45, 75 45, 75 35" fill="none" stroke="#DC2626" strokeWidth="9" strokeLinecap="round" />
            <path d="M25 65 C25 55, 45 55, 50 65 C55 75, 75 75, 75 65" fill="none" stroke="#1E40AF" strokeWidth="9" strokeLinecap="round" />
            <text x="50" y="55" textAnchor="middle" dominantBaseline="middle" fill="#1E3A8A" fontWeight="900" fontSize="20">
              SSI
            </text>
          </svg>
        </div>
      );

    case 'TCB':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-white border border-[#E1E7EF] shadow-xs p-1 ${sizeClasses} ${className}`}>
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <rect width="100" height="100" rx="18" fill="#FFFFFF" />
            {/* Dual Red Diamond Squares */}
            <rect x="24" y="24" width="30" height="30" fill="#E11D48" rx="4" transform="rotate(45 39 39)" />
            <rect x="46" y="46" width="30" height="30" fill="#BE123C" rx="4" transform="rotate(45 61 61)" />
          </svg>
        </div>
      );

    case 'VHM':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-[#1E3A8A] border border-[#172554] shadow-xs p-1 ${sizeClasses} ${className}`}>
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <rect width="100" height="100" rx="18" fill="#1E3A8A" />
            {/* Golden V Wing */}
            <path d="M22 30 L50 78 L78 30 L66 30 L50 60 L34 30 Z" fill="#F59E0B" />
            <path d="M30 30 L50 66 L70 30" fill="none" stroke="#FBBF24" strokeWidth="3" />
          </svg>
        </div>
      );

    case 'DGC':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-white border border-[#E1E7EF] shadow-xs p-1 ${sizeClasses} ${className}`}>
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <rect width="100" height="100" rx="18" fill="#FFFFFF" />
            <circle cx="50" cy="50" r="32" fill="none" stroke="#0284C7" strokeWidth="6" strokeDasharray="6,4" />
            <circle cx="50" cy="50" r="14" fill="#0EA5E9" />
            <text x="50" y="88" textAnchor="middle" fill="#0369A1" fontWeight="900" fontSize="18">
              DGC
            </text>
          </svg>
        </div>
      );

    case 'MBB':
      return (
        <div className={`relative flex items-center justify-center rounded-xl bg-[#002D72] border border-[#001D4A] shadow-xs p-1 ${sizeClasses} ${className}`}>
          <svg viewBox="0 0 100 100" className="w-full h-full">
            <rect width="100" height="100" rx="18" fill="#002D72" />
            {/* MB Red & White Star elements */}
            <polygon points="50,22 57,40 76,40 60,52 66,70 50,58 34,70 40,52 24,40 43,40" fill="#EF4444" />
            <text x="50" y="88" textAnchor="middle" fill="#FFFFFF" fontWeight="900" fontSize="20">
              MB
            </text>
          </svg>
        </div>
      );

    default:
      return (
        <div className={`flex items-center justify-center rounded-xl bg-[#1A56DB] text-white font-extrabold shadow-xs ${sizeClasses} ${className}`}>
          {symbol.slice(0, 3)}
        </div>
      );
  }
};
