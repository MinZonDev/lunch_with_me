'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { isLoggedIn } from '@/lib/auth';

const PUBLIC_PATHS = ['/login', '/register', '/forgot-password', '/reset-password'];

export default function AuthGuard({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (PUBLIC_PATHS.includes(pathname)) {
      setChecked(true);
      return;
    }

    if (!isLoggedIn()) {
      router.replace('/login');
    } else {
      setChecked(true);
    }
  }, [pathname, router]);

  if (!checked && !PUBLIC_PATHS.includes(pathname)) {
    return (
      <div className="loading-spinner">
        <div className="spinner" />
      </div>
    );
  }

  return children;
}
