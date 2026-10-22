"use client";
import { useState } from "react";
export default function Page(){const [n,setN]=useState(0);return(<main className="min-h-screen bg-[#090a0d] text-[#f0f2f5] p-8"><h1 className="text-4xl font-semibold">Orvima</h1><p className="mt-4 text-[#a0a8b3]">Count {n}</p><button onClick={()=>setN(n+1)} className="mt-4 px-4 py-2 rounded bg-[#f5a524] text-[#141004]">Click</button></main>);};
