const KEYWORDS = new Set([
  'def', 'class', 'import', 'from', 'as', 'if', 'elif', 'else',
  'for', 'while', 'try', 'except', 'finally', 'with', 'return',
  'yield', 'raise', 'pass', 'break', 'continue', 'and', 'or',
  'not', 'in', 'is', 'lambda', 'None', 'True', 'False',
  'global', 'nonlocal', 'assert', 'del', 'async', 'await',
])

const BUILTINS = new Set([
  'print', 'len', 'range', 'int', 'str', 'list', 'dict', 'set',
  'tuple', 'float', 'bool', 'type', 'isinstance', 'hasattr',
  'getattr', 'setattr', 'open', 'input', 'map', 'filter', 'zip',
  'enumerate', 'sorted', 'reversed', 'sum', 'min', 'max', 'abs',
  'round', 'any', 'all', 'super', 'self', 'cls', 'iter', 'next',
  'bytes', 'bytearray', 'memoryview', 'complex', 'frozenset',
  'object', 'property', 'staticmethod', 'classmethod', 'ValueError',
  'TypeError', 'KeyError', 'IndexError', 'Exception', 'RuntimeError',
  'FileNotFoundError', 'json', 'os', 'sys', 're', 'math', 'datetime',
  'pathlib', 'Path',
])

export function highlightPython(code: string): string {
  const lines = code.split('\n')
  return lines.map((line, i) => {
    const html = escapeHtml(line)
    const highlighted = tokenizeLine(html)
    return `<div class="py-line"><span class="py-ln">${i + 1}</span><span class="py-tokens">${highlighted || ' '}</span></div>`
  }).join('')
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function tokenizeLine(line: string): string {
  // Order matters: strings before keywords, comments before strings
  return line.replace(
    /("""[\s\S]*?"""|'''[\s\S]*?'''|[rfb]?"(?:[^"\\]|\\.)*"|[rfb]?'(?:[^'\\]|\\.)*'|#[^\n]*|\b\d+\.?\d*\b|\b[a-zA-Z_]\w*\b|[^\s\w]+)/g,
    (match) => {
      // Triple-quoted strings
      if (/^(?:"""|''')/.test(match)) return `<span class="py-str">${match}</span>`
      // Regular strings / f-strings
      if (/^[rfb]?"/.test(match) || /^[rfb]?'/.test(match)) return `<span class="py-str">${match}</span>`
      // Comments
      if (match.startsWith('#')) return `<span class="py-comment">${match}</span>`
      // Numbers
      if (/^\d/.test(match)) return `<span class="py-num">${match}</span>`
      // Keywords
      if (KEYWORDS.has(match)) return `<span class="py-kw">${match}</span>`
      // Builtins
      if (BUILTINS.has(match)) return `<span class="py-builtin">${match}</span>`
      return match
    }
  )
}
