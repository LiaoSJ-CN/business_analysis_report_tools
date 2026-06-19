import { useEffect, useRef } from 'react';
import { EditorState } from '@codemirror/state';
import { EditorView, keymap, placeholder } from '@codemirror/view';
import { sql, SQLDialect } from '@codemirror/lang-sql';
import { autocompletion, completionKeymap } from '@codemirror/autocomplete';
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands';
import { syntaxHighlighting, HighlightStyle } from '@codemirror/language';
import { tags as t } from '@lezer/highlight';
import { oneDark } from '@codemirror/theme-one-dark';

const customSql = SQLDialect.define({
  keywords: 'select,from,where,and,or,order,by,group,having,limit,join,left,right,inner,outer,on,as,distinct,count,sum,avg,max,min,in,not,null,like,is,union,all,case,when,then,else,end,between,exists,cross,full,self',
  builtin: 'count,sum,avg,max,min,upper,lower,trim,length,concat,substring,now,date,time,datetime,coalesce,nullif',
});

// Custom highlight style for SQL
const sqlHighlightStyle = HighlightStyle.define([
  { tag: t.keyword, color: '#0550ae', fontWeight: 'bold' },
  { tag: t.string, color: '#0b9c31' },
  { tag: t.number, color: '#0550ae' },
  { tag: t.operator, color: '#d73a49' },
  { tag: t.comment, color: '#6b778c', fontStyle: 'italic' },
  { tag: t.function(t.variableName), color: '#6639ba' },
  { tag: t.typeName, color: '#e36209' },
]);

interface SqlEditorProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  height?: string;
  dark?: boolean;
}

export default function SqlEditor({ value, onChange, placeholder: placeholderText, height = '200px', dark = false }: SqlEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const extensions = [
      history(),
      sql({ dialect: customSql }),
      syntaxHighlighting(sqlHighlightStyle),
      autocompletion(),
      keymap.of([...defaultKeymap, ...historyKeymap, ...completionKeymap]),
      placeholder(placeholderText || 'SELECT * FROM ...'),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          onChange(update.state.doc.toString());
        }
      }),
      EditorView.theme({
        '&': { height, fontSize: '14px' },
        '.cm-scroller': { overflow: 'auto', fontFamily: 'monospace' },
        '.cm-content': { caretColor: '#1890ff' },
      }),
    ];

    if (dark) {
      extensions.push(oneDark);
    }

    const state = EditorState.create({
      doc: value,
      extensions,
    });

    const view = new EditorView({
      state,
      parent: containerRef.current,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync external value changes
  useEffect(() => {
    const view = viewRef.current;
    if (view && value !== view.state.doc.toString()) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: value },
      });
    }
  }, [value]);

  return (
    <div
      ref={containerRef}
      style={{
        border: '1px solid #d9d9d9',
        borderRadius: 6,
        overflow: 'hidden',
      }}
    />
  );
}
