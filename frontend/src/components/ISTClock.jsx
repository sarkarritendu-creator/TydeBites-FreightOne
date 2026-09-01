import React, { useState, useEffect } from 'react';

export default function ISTClock() {
  const [time, setTime] = useState('');

  useEffect(() => {
    // Set initial time immediately
    const updateTime = () => {
      setTime(new Date().toLocaleTimeString('en-US', {
        timeZone: 'Asia/Kolkata',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      }));
    };

    updateTime();
    const timer = setInterval(updateTime, 1000);

    return () => clearInterval(timer);
  }, []);

  return <>{time ? `IST ${time}` : 'Loading...'}</>;
}