'use client';

import { useEffect, useRef } from 'react';
import { collection, onSnapshot, query, where } from 'firebase/firestore';
import { db, ensureFirebaseAuth } from './firebaseClient';

// Listens for changes to one or more daily_orders and their order_items in
// Firestore and calls onChange() whenever something changes elsewhere. The
// REST API stays the source of truth for reads (it computes joins/costs);
// this just tells the page when to refetch, instead of polling on a timer.
//
// orderIds may be a single id or an array of ids (e.g. all of today's menus).
export function useOrderRealtime(orderIds, onChange) {
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const ids = (Array.isArray(orderIds) ? orderIds : [orderIds]).filter((id) => id != null);
  const idsKey = [...ids].sort().join(',');

  useEffect(() => {
    if (ids.length === 0) return undefined;

    let cancelled = false;
    let unsubOrder = null;
    let unsubItems = null;
    let skippedFirstOrder = false;
    let skippedFirstItems = false;

    ensureFirebaseAuth()
      .then(() => {
        if (cancelled) return;

        unsubOrder = onSnapshot(
          query(collection(db, 'daily_orders'), where('id', 'in', ids)),
          () => {
            if (!skippedFirstOrder) { skippedFirstOrder = true; return; }
            onChangeRef.current();
          }
        );

        unsubItems = onSnapshot(
          query(collection(db, 'order_items'), where('daily_order_id', 'in', ids)),
          () => {
            if (!skippedFirstItems) { skippedFirstItems = true; return; }
            onChangeRef.current();
          }
        );
      })
      .catch((err) => console.error('Realtime auth failed:', err));

    return () => {
      cancelled = true;
      if (unsubOrder) unsubOrder();
      if (unsubItems) unsubItems();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idsKey]);
}
