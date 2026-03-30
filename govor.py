#!/usr/bin/env python3
"""
govor.py — Говореща програма от Борислав Захариев
===================================================
Python port of the legendary Bulgarian speech synthesizer
originally written for the Pravets 8 (Apple II clone) in the late 1980s.

The original program used 1-bit audio synthesis by toggling the Apple II
speaker at precise intervals controlled by 6502 machine code. Each phoneme
is stored as a waveform table where bytes encode timing values for speaker
half-cycles, creating formant-like sounds from a simple square wave.

Usage:
    python govor.py "zdrasti"          # Speak text, save to WAV
    python govor.py "здрасти"          # Also accepts Cyrillic input
    python govor.py -i                 # Interactive mode
    python govor.py --demo             # Speak the classic intro
    python govor.py --info             # Show character mapping

Transliteration (Latin → Bulgarian phoneme):
    a=а  b=б  c=ц  d=д  e=е  f=ф  g=г  h=х  i=и  j=ж  k=к  l=л  m=м
    n=н  o=о  p=п  q=я  r=р  s=с  t=т  u=у  v=в  w=ъ  x=ж  y=ь  z=з
    [=ш  ]=щ  ^=ч  `=ю

Original (c) Borislav Zachariev, late 1980s
Python port created by reverse-engineering the 6502 binary from GOVOR.dsk
"""

import struct
import wave
import sys

# ============================================================================
#  CONFIGURATION
# ============================================================================

SAMPLE_RATE = 22050       # Output sample rate (Hz)
CPU_FREQ    = 1023000     # Apple II CPU frequency (Hz)
DEFAULT_SPD = 8           # Default inner-loop speed (1-12)
AMPLITUDE   = 24000       # 16-bit output amplitude

# ============================================================================
#  PHONEME WAVEFORM DATA — extracted from GOVOR.dsk
# ============================================================================
# Each value is the raw waveform exactly as stored in the Pravets 8 binary.
# Format per phoneme:
#   [optional 0xFF]  — if present, use "nibble mode" (two half-cycles/byte)
#   [repeat_count]   — how many times to loop the waveform
#   [data bytes ...]  — waveform timing values
#
# Nibble mode (after 0xFF): high nibble = 1st half-cycle, low = 2nd
# Byte mode  (no 0xFF):     full byte   = single speaker-toggle timing
# A nibble/byte of 0 means "no toggle" (brief silence in that slot).

_P = {
    '[': 'ff0135131123324333343334234433424343242551333342425334243524333421242334242433433334334334333433112224212212211222524234343334333321143344252542221333221122112222321225212132243424342434334334333261342424211224221233221222211212223322121222112523534432123434323115243334343434333312134243422222123345222133352443334343245233343211312123122343211236242425242222132324112422122222333232121221333442335223222322212112211242212222122122121422212311221212122412112532344322322245421122533322142112212224343432212332242433333323442242112234254121243252423421221125322124231412224422421212123211522333421124333321222221222122222243424323122221432212322222443311232114232322343335333332221221122312112221241222',
    '\\':'',
    ']': 'ff0135131123324333343334234433424343242551333342425334243524333421242334242433433334334334333433112224212212211222524234343334333321143344252542221333221122112222321225212132243424342434334334333261342424211224221233221222211212223322121222112523534432123434323115243334343434333312134243422222123345222133352443334343245233343211312123122343211236242425242222132324112422122222333232121221333442335223222322212112211242212222122122121422212311221212122412112532344322322245421122533322142112212224343432212332242433333323442242112234254121243252423421221125322124231412224422421212123211522333421124333321222221222122222243424323122221432212322222443311232114232322343335333332221221122312112221241222424400ff01000096f2222241b6222231262622222212223222d121225111222222132161412121222222213222312147',
    '^': 'ff01312211212211222423532221222222112234232112224222222221231222332322212524211324333343222312222623233333332c33342425434423422213435222212343333432122211234323121333333222212221212231124334333433333332222222222112122222122242322212232425233423522233222313242522122122243364212143212222222254231123523322222252234432221224235242213243221221122523121222212323433334333352821222221123',
    '_': '0123131112',
    '`': '01285002022b502e50030229530102295301022a5202012a50010203022c490203020104012b390115020203022a470104010203022f4c06013040010e03022e35010501050303060204032e41030403030502040129310107010102010201010201010204050233370b0201010307010204012a31020407010202070201020402060125310503020502020301020402012e31030303040102010a010307012533041a0501262d09182d330418040126330416020326320714292e0a19232c0bbb232a0c192224121a1f231419202214191f2015191f20151a1e20151b1e1d161b1e1d161b1d1d161a1c1d161a1c1c16011b1e14181b1d14',
    'a': '010c0b09120e0c0a0d0a0b0a160f0b0a0b0a0c09180e0b0a0b0a0b09190e0b090b0b0b090d04090d0a0a0b0b0a0a0c050a0c0a0b0b0a0b090c050c0b0a0b0b0a0a0a0b060d0b090b0b0a0b0a0a070f0a0a0a0b0a0b0a0907120a090a0c080c0a0a06140a090b0c090a090b06170b080b0b0a0a090b08160a090b0b080c0809071c0a090b0b080c0909071e0a090a0b080b0a09072208090a0d060e09070b0527070b0b084c09080a',
    'b': '014a3e5a17513e5a2c014f395438523e50414d5e323a5359303b4e3e534e434057404a40533a554b4240576f180201320805020604062a220418354e291f0b3122160a1905261c0f12140d1a0206170f',
    'c': 'ff010000000912c1b1411151215121c1c511212561412111052121121223a116211121124121f465611124b3611161127111212181212121624121712141112121212181212181512151211131019121216111311122216122211271513121c35111611121116161211213211212131122112111112111232131212121211151112131211151218171211112112141411111e111211111111211111131212171212121312111411222141121191141',
    'd': '0135292aad2a5b285e3364365d2d2d181c33301626306038633632151d333273663661393e04020502010e02020103291e010801030112030d02020107010202022b28121802020102010e271e1e21010d211b1933211a1601032f251b1c280701261b170104230401321d1c24090f1e',
    'e': '01040203040418020304021202182f0205231213321a1214120a1d18121112101f181210111122170f13101324160e13111226160e13101327170d13101327160e1310132716120f12112717120f140f2617140f1311221d1212120f1f1d17133d265741942b1530',
    'f': 'ff0112321a3211212261f312123c21212432225e1b1d131322188132262151367311211212121122811d121f1312121212221218221212181212117231771165151d111918121c9121d121917151b22222121f1313251115912311124a12926c1552721248122214172122122219221412225121c223632142122212542212212122114a122219121618162c421212b1a714121211253332212421224b612213111242171121222121531222181148831812112162121121151126e1121212111b5b82d3117941467762151b62181215',
    'g': '0104050504050504050503050505040405060201020d0505370102060301010e04050201022d2a01030204030306020102020201030201020301020205050201022602011d020201030103011202020201110202040601241901060101061d0f05050701021b03020f0306040404060207010201050206010201060102010602020102040103012019131301020103010301020102010902010202231a122002030113201812190b151c14131809191b',
    'h': 'ff01676b762a5878679521221969675a4851768769378b12486646a687c212261777767686521a221e3312722223986113977a2b567a289468669667774857212759548a495963531576688731362193321422123313221912131a127621171231676313123a666313123217a2217397685969546778576768521677761176686b171222222236312957773117786878731221256869522a927938785b71252212221c8784c67687',
    'i': '01231b1727241b1b23241c1b23251d1923251d18220203221c1a200303221c18210402221c1921271c1921251e1823231e1923231d1922241e1723251d1625241a172a211a03020b32241a0c37231a0337320402433e3a3f482d3e454a4d4e86',
    'j': '01285002022b502e50030229530102295301022a5202012a50010203022c490203020104012b390115020203022a470104010203022f4c06013040010e03022e35010501050303060204032e41030403',
    'k': 'ff010000005242616199edb466a17165554e657145a572142503552221863e661225525637445534615842817168344251e1a4444252215221728462836111',
    'l': '01201e1a1d1a1a1e221f181a1e1a18011a01021e1e1a1e221d1b1f201e191e211e181e211d191d211e181e201d171e201d181d201e161d211d161d201d171c1f010201020302010a0302010102010202',
    'm': '011812113f1e11103c275521542554215821562216083724150a342056284d3f3741383a42364431443744414a214e28',
    'n': '012c20383222164b4b2a542e542b542f522e51305231532d532b532c512e502d4e2d4f2c4e2c4d2e4d2d4e2c4e284f294c2a4a270d102b1f1415291f1315291f',
    'o': '0137160a0d110b030a36150a0f0e0c060834140a110d0c060835120a120d0c0608321309130d0c060732120a130e0c05082f120b130d182f130c120e1631120d120e1431130e110e1531130f100f130e032013110f10120b0613030a12120e11010d042113110e120d0c0513050915100e110a0b0712080514120c120a2f1d0f0d1106282e03041b0633353c020b120122020202120302020203010204010302',
    'p': '01000f100a0e06210110150e12020201020205030204020715010b0603253a560a0f0a0e0b09170d0a0e0a0f0a0a19',
    'q': '0111192024111a211e151b1d1e151e1b1b161c1b1a161e1a17161d1c181321020316151417060d14130f18081010130e0f0c17140f0c0f0c21110e0d0e0c20110b0c0f0b230e0c0e010c0b09120e0c0a0d0a0b0a160f0b0a0b0a0c09180e0b0a0b0a0b09190e0b090b0b0b090d04090d0a0a0b0b0a0a0c050a0c0a0b0b0a0b090c050c0b0a0b0b0a0a0a0b060d0b090b0b0a0b0a0a070f0a0a0a0b0a0b0a0907120a090a0c080c0a0a06140a090b0c090a090b06170b080b0b0a0a090b08160a090b0b080c0809071c0a090b0b080c0909071e0a090a0b080b0a09072208090a0d060e09070b0527070b0b084c09080a',
    'r': '011d1316301b1217341a13151a05171b1615180c082c653c5f3717020503020303030d01040405020902052318162d2118172e201b162b05011e181828231b17',
    's': 'ff0123131112112322121212221221212221222121222121221221132121221212312122121123122313114221412111212121112111211211221121112112121112112121322121121111212112112111211221121112121231212112212221221212212212121231211121121121222212122212121612112122211211111212122221221221221211211121111111215121212212212123121212211121321272212611212111212121112112121121111211212122112122111111212121214112122122112312121212212121212111111221112131211221112112311321112111121211121211112112112112212131121134112111213211212311121111221222112121112111212121111121213112121141111211211151112162112121121111112131141221121122211311121212112222112112211111211211121311211131121121312121311111111121124221211311612111121121212211112111211121212112111212112121121122121111112211151121121123111111311211321121121211112121212111121111225122112131221112112221311312111221111111112121211121',
    't': 'ff01000096f2222241b6222231262622222212223222d121225111222222132161412121222222213222312147',
    'u': '011b1e14181b1d14181b1d12181c1b16151c1e0e1b1a1c12161c1b12161b1c11151c2208161c200b141c3d1e3d1b3d1c3c1c3e1b1c09191a3d191d081c183f19',
    'v': '0202201f0b02010b020302020102020201020202020101020203010202020102020201051d210b0c010501020102020202020202010202030101040202060202020202011e1c0b03010c020302030202020202030202020102020302010202020205201c03010a0c0202020101030204020302020101020303030303030303030401181b04020a0201060102010201050202020202020202020203020202010202030201020202021e1a0202030402030306010301020103020202020104020102020203010202020202010702031d1c020304020305010301020102020202020204020201030202010301030105010301020202010202021c1a01020c030202',
    'w': '01010e271e1e21010d211b1933211a1601032f251b1c280701261b170104230401321d1c24090f1e1f221c030204111f2321272e37032b030204082434202b29340f2903042434101a0213231e1823070a1f1c0b090c2d1d12100f10261a1012101125170b12111227160c1010122a13',
    'x': '01285002022b502e50030229530102295301022a5202012a50010203022c490203020104012b390115020203022a470104010203022f4c06013040010e03022e35010501050303060204032e41030403',
    'y': '011c14131809191b1b2616131b2617121c2517121d2516131b2418131c2517131d2516141b2718121d2617131c2717131d2717131c2817131c2a17121d2b17121c2d16121c2f17111c172a121c080808',
    'z': '0202010401010201261c010202010102011701020101010202010102020102010201020101020102020101020101010101050101010201011e180102080f010201050102020101020102010101020102010501020101040201010102010201010102010201011e18010b0110010201030102010101020102010201020103010202010201020102010203010201020101221a0103010201020102010201040102010101020101010201020101010201010102010501020102010101040101010101010201020101020102221d01010102010201020101020101050106010101020103010201020107020201010201020101020101010201010201020122240102',
    '{': '01', '|': '01', '}': '01', '~': '01',
}

PHONEME_DATA = {k: bytes.fromhex(v) for k, v in _P.items()}

CHAR_NAMES = {
    '[': 'ш (sha)',  '\\': '(silent)', ']': 'щ (shta)',  '^': 'ч (cha)',
    '_': '(pause)',  '`': 'ю (yu)',    'a': 'а (a)',     'b': 'б (b)',
    'c': 'ц (ts)',   'd': 'д (d)',     'e': 'е (e)',     'f': 'ф (f)',
    'g': 'г (g)',    'h': 'х (h)',     'i': 'и (i)',     'j': 'ж (zh)',
    'k': 'к (k)',    'l': 'л (l)',     'm': 'м (m)',     'n': 'н (n)',
    'o': 'о (o)',    'p': 'п (p)',     'q': 'я (ya)',    'r': 'р (r)',
    's': 'с (s)',    't': 'т (t)',     'u': 'у (u)',     'v': 'в (v)',
    'w': 'ъ (uh)',   'x': 'ж (zh)',    'y': 'ь (soft)',  'z': 'з (z)',
}

NUMBER_WORDS = [
    'nula', 'edno', 'dwe', 'tri', '^etiri',
    'pet', '[est', 'sedem', 'osem', 'dewet',
]


# ============================================================================
#  SYNTHESIS ENGINE
# ============================================================================

class GovorSynth:
    """
    Emulates the Pravets 8 / Apple II speaker-toggle synthesis.

    The Apple II has a 1-bit speaker toggled by writing to $C030.
    By controlling timing between toggles, the original 6502 code creates
    variable-frequency square waves that approximate speech formants.

    Two playback modes in the original binary:
      * Nibble mode (0xFF prefix) — byte split into two 4-bit half-cycle
        timing values.  Used for consonants / fricatives.
      * Byte mode (no prefix) — full byte = one toggle timing.
        Used for vowels / voiced sounds.
    """

    def __init__(self, sample_rate=SAMPLE_RATE, speed=DEFAULT_SPD):
        self.sample_rate = sample_rate
        self.speed = speed
        self.speaker = 1
        self.samples = []

    def _emit(self, cpu_cycles):
        n = max(1, round(cpu_cycles * self.sample_rate / CPU_FREQ))
        self.samples.extend([self.speaker * AMPLITUDE] * n)

    def _toggle(self):
        self.speaker = -self.speaker

    def _silence(self, cpu_cycles):
        n = max(1, round(cpu_cycles * self.sample_rate / CPU_FREQ))
        self.samples.extend([0] * n)

    def _play_half_cycle(self, value, speed):
        if value <= 0:
            return
        self._toggle()
        cycles = 10 + value * (5 * speed + 6)
        self._emit(cycles)

    def play_phoneme(self, char, speed=None):
        if speed is None:
            speed = self.speed
        if char == ' ':
            self._silence(speed * 2000)
            return
        raw = PHONEME_DATA.get(char)
        if not raw or len(raw) < 2:
            return

        pos = 0
        nibble_mode = False
        if raw[pos] == 0xFF:
            nibble_mode = True
            pos += 1
        if pos >= len(raw):
            return

        repeat = raw[pos] or 1
        pos += 1
        wave_start = pos

        for _ in range(repeat):
            p = wave_start
            while p < len(raw):
                b = raw[p]; p += 1
                if nibble_mode:
                    hi = (b >> 4) & 0x0F
                    lo = b & 0x0F
                    if b == 0:
                        self._emit(30)
                        continue
                    if hi > 0:
                        self._play_half_cycle(hi, speed)
                    else:
                        self._emit(5 * speed)
                    if lo > 0:
                        self._play_half_cycle(lo, speed)
                    else:
                        self._emit(5 * speed)
                else:
                    if b == 0:
                        self._emit(30)
                        continue
                    self._play_half_cycle(b, speed)

    def speak(self, text, speed=None):
        spd = speed if speed is not None else self.speed
        for ch in text:
            if   ch == '/': spd = max(1, spd - 1)
            elif ch == ':': spd = min(15, spd + 1)
            elif ch.isdigit(): spd = int(ch) + 3
            elif ch == ' ': self._silence(spd * 2000)
            elif ch in PHONEME_DATA: self.play_phoneme(ch, spd)

    def save(self, filename):
        with wave.open(filename, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            clamped = [max(-32767, min(32767, s)) for s in self.samples]
            wf.writeframes(struct.pack(f'<{len(clamped)}h', *clamped))
        dur = len(self.samples) / self.sample_rate
        print(f"  -> {filename}  ({dur:.2f}s, {len(self.samples)} samples)")

    def reset(self):
        self.samples.clear()
        self.speaker = 1


# ============================================================================
#  CYRILLIC TRANSLITERATION
# ============================================================================

_CYR = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
    'ж': 'j', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l',
    'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's',
    'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': '^',
    'ш': '[', 'щ': ']', 'ъ': 'w', 'ь': 'y', 'ю': '`', 'я': 'q',
}

def to_govor(text):
    out = []
    for ch in text.lower():
        out.append(_CYR.get(ch, ch if (ch in PHONEME_DATA or ch == ' ') else ''))
    return ''.join(out)


# ============================================================================
#  CLI
# ============================================================================

def speak_to_file(text, filename='govor_output.wav', speed=DEFAULT_SPD):
    govor_text = to_govor(text)
    synth = GovorSynth(speed=speed)
    synth.speak(govor_text)
    if not synth.samples:
        print("Warning: no audio generated.")
        return None
    print(f'  text : "{text}"')
    print(f'  govor: "{govor_text}"')
    synth.save(filename)
    return filename


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description='Govoreshta programa ot Borislav Zahariev - Python port')
    ap.add_argument('text', nargs='?', help='Text to speak')
    ap.add_argument('-o', '--output', default='govor_output.wav')
    ap.add_argument('-s', '--speed', type=int, default=DEFAULT_SPD,
                    help='Speed 1-12 (default 8)')
    ap.add_argument('-i', '--interactive', action='store_true')
    ap.add_argument('--demo', action='store_true')
    ap.add_argument('--info', action='store_true')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    if args.info:
        print("=== GOVORESHTA PROGRAMA - Phoneme Map ===\n")
        for ch in sorted(CHAR_NAMES):
            d = PHONEME_DATA.get(ch, b'')
            if len(d) > 1:
                mode = 'nibble' if d[0] == 0xFF else 'byte'
                print(f"  '{ch}'  ->  {CHAR_NAMES[ch]:14s}  {len(d):4d}B  {mode}")
        return

    if args.all:
        synth = GovorSynth(speed=args.speed)
        for ch in sorted(PHONEME_DATA):
            if len(PHONEME_DATA[ch]) > 1:
                synth.play_phoneme(ch)
                synth._silence(args.speed * 1500)
        synth.save(args.output)
        return

    if args.demo:
        speak_to_file('gowore]a programa ot borislaw zahariew',
                       args.output, args.speed)
        return

    if args.interactive:
        print("=== GOVORESHTA PROGRAMA - Interactive ===")
        print("Type text (Latin or Cyrillic).  'q' to quit.\n")
        n = 0
        while True:
            try:
                t = input('govor> ').strip()
            except (EOFError, KeyboardInterrupt):
                print(); break
            if t.lower() == 'q':
                break
            if t:
                n += 1
                speak_to_file(t, f'govor_{n:03d}.wav', args.speed)
        return

    if args.text:
        speak_to_file(args.text, args.output, args.speed)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
