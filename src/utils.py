import math

class GuildWarsTemplateDecoder:
    def __init__(self, code):
        self.code = code.strip()
        self.base64_map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        self.binary_stream = ""
        self.pos = 0

    def _base64_to_binary_stream(self):
        stream = []
        for char in self.code:
            if char not in self.base64_map: continue
            val = self.base64_map.index(char)
            bin_str = f"{val:06b}"
            stream.append(bin_str[::-1])
        self.binary_stream = "".join(stream)

    def _read_bits(self, length):
        if self.pos + length > len(self.binary_stream): return 0 
        chunk = self.binary_stream[self.pos : self.pos + length]
        self.pos += length
        reversed_chunk = chunk[::-1]
        return int(reversed_chunk, 2)

    def decode(self):
        try:
            self._base64_to_binary_stream()
            template_type = self._read_bits(4)
            version = self._read_bits(4)
            prof_bit_code = self._read_bits(2)
            prof_bits = (prof_bit_code * 2) + 4
            primary_prof = self._read_bits(prof_bits)
            secondary_prof = self._read_bits(prof_bits)
            count_attributes = self._read_bits(4)
            attr_bit_code = self._read_bits(4)
            attr_id_bits = attr_bit_code + 4
            attributes = []
            for _ in range(count_attributes):
                attributes.append([self._read_bits(attr_id_bits), self._read_bits(4)])
            skill_bit_code = self._read_bits(4)
            skill_id_bits = skill_bit_code + 8
            skills = [self._read_bits(skill_id_bits) for _ in range(8)]
            return {
                "header": {"type": template_type, "version": version},
                "profession": {"primary": primary_prof, "secondary": secondary_prof},
                "attributes": attributes,
                "skills": skills
            }
        except: return None

class GuildWarsTemplateEncoder:
    def __init__(self, data):
        self.data = data
        self.base64_map = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        self.binary_stream = ""

    def _write_bits(self, value, length):
        v = int(value)
        if v >= (1 << length): v = (1 << length) - 1
        bin_str = f"{v:0{length}b}"
        self.binary_stream += bin_str[::-1]

    def _get_min_bits_for_value(self, value):
        v = int(value)
        if v == 0: return 0
        return v.bit_length()

    def encode(self):
        header = self.data.get('header', {'type': 14, 'version': 0})
        self._write_bits(header.get('type', 14), 4)
        self._write_bits(header.get('version', 0), 4)
        prof = self.data.get('profession', {'primary': 0, 'secondary': 0})
        prim, sec = int(prof.get('primary', 0)), int(prof.get('secondary', 0))
        max_prof_id = max(prim, sec)
        prof_bits_needed = max(4, self._get_min_bits_for_value(max_prof_id))
        prof_bit_code = max(0, math.ceil((prof_bits_needed - 4) / 2))
        if prof_bit_code > 3: prof_bit_code = 3 
        real_prof_bits = (prof_bit_code * 2) + 4
        self._write_bits(prof_bit_code, 2)
        self._write_bits(prim, real_prof_bits)
        self._write_bits(sec, real_prof_bits)
        attrs = self.data.get('attributes', [])
        self._write_bits(len(attrs), 4)
        if len(attrs) > 0:
            max_attr_id = max([int(a[0]) for a in attrs])
            attr_bits_needed = max(4, self._get_min_bits_for_value(max_attr_id))
            attr_bit_code = max(0, attr_bits_needed - 4)
            if attr_bit_code > 15: attr_bit_code = 15
        else: attr_bit_code = 0
        self._write_bits(attr_bit_code, 4)
        for attr in attrs:
            self._write_bits(attr[0], attr_bit_code + 4)
            self._write_bits(attr[1], 4)
        skills = self.data.get('skills', [0]*8)
        max_skill_id = max([int(s) for s in skills])
        skill_bits_needed = max(8, self._get_min_bits_for_value(max_skill_id))
        skill_bit_code = max(0, skill_bits_needed - 8)
        if skill_bit_code > 15: skill_bit_code = 15
        self._write_bits(skill_bit_code, 4)
        for sid in skills: self._write_bits(sid, skill_bit_code + 8)
        remainder = len(self.binary_stream) % 6
        if remainder != 0: self.binary_stream += "0" * (6 - remainder)
        b64 = ""
        for i in range(0, len(self.binary_stream), 6):
            chunk = self.binary_stream[i : i + 6]
            b64 += self.base64_map[int(chunk[::-1], 2)]
        return b64
