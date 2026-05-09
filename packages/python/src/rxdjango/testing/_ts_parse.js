// Parses a TypeScript file with the official compiler API and prints a
// JSON description of its top-level classes to stdout. Invoked by
// rxdjango.testing.ts_ast.parse_ts_file.
//
// Usage: node _ts_parse.js <path-to-ts-file>
const fs = require('fs');
const ts = require('typescript');

function nodeText(node, source) {
  return node.getText(source);
}

function describeType(typeNode, source) {
  if (!typeNode) return null;
  return nodeText(typeNode, source);
}

function describeInitializer(init, source) {
  if (!init) return null;
  return { text: nodeText(init, source), kind: ts.SyntaxKind[init.kind] };
}

function describeClass(node, source) {
  const heritage = [];
  if (node.heritageClauses) {
    for (const clause of node.heritageClauses) {
      const keyword = clause.token === ts.SyntaxKind.ExtendsKeyword ? 'extends' : 'implements';
      for (const t of clause.types) {
        heritage.push({ kind: keyword, name: nodeText(t.expression, source) });
      }
    }
  }

  const members = [];
  for (const member of node.members) {
    if (ts.isPropertyDeclaration(member)) {
      members.push({
        kind: 'property',
        name: member.name.getText(source),
        type: describeType(member.type, source),
        initializer: describeInitializer(member.initializer, source),
        optional: !!member.questionToken,
        readonly: !!(member.modifiers || []).find(m => m.kind === ts.SyntaxKind.ReadonlyKeyword),
      });
    } else if (ts.isMethodDeclaration(member)) {
      members.push({
        kind: 'method',
        name: member.name.getText(source),
        params: member.parameters.map(p => ({
          name: p.name.getText(source),
          type: describeType(p.type, source),
        })),
        returnType: describeType(member.type, source),
      });
    }
  }

  return {
    name: node.name ? node.name.text : null,
    exported: !!(node.modifiers || []).find(m => m.kind === ts.SyntaxKind.ExportKeyword),
    heritage,
    members,
  };
}

function describeImport(node, source) {
  if (!node.importClause) return null;
  const named = [];
  if (node.importClause.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) {
    for (const el of node.importClause.namedBindings.elements) {
      named.push(el.name.text);
    }
  }
  return {
    module: node.moduleSpecifier.text,
    default: node.importClause.name ? node.importClause.name.text : null,
    named,
  };
}

function main() {
  const filePath = process.argv[2];
  if (!filePath) {
    console.error('usage: _ts_parse.js <file>');
    process.exit(2);
  }
  const text = fs.readFileSync(filePath, 'utf8');
  const source = ts.createSourceFile(filePath, text, ts.ScriptTarget.Latest, true);

  const diagnostics = source.parseDiagnostics || [];
  const result = {
    file: filePath,
    classes: [],
    imports: [],
    parseErrors: diagnostics.map(d => ({
      message: ts.flattenDiagnosticMessageText(d.messageText, '\n'),
      start: d.start,
      length: d.length,
    })),
  };

  ts.forEachChild(source, (node) => {
    if (ts.isClassDeclaration(node)) {
      result.classes.push(describeClass(node, source));
    } else if (ts.isImportDeclaration(node)) {
      const imp = describeImport(node, source);
      if (imp) result.imports.push(imp);
    }
  });

  process.stdout.write(JSON.stringify(result));
}

main();
