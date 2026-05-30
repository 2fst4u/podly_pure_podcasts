import { useState } from 'react';
import { useConfigContext } from '../ConfigContext';
import { Section, Field, SaveButton } from '../shared';

export default function AppSection() {
  const { pending, setField, handleSave, isSaving } = useConfigContext();
  const [tavilyKeyInput, setTavilyKeyInput] = useState('');

  if (!pending) return null;

  return (
    <div className="space-y-6">
      <Section title="App">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Field label="Feed Refresh Background Interval (min)">
            <input
              className="input"
              type="number"
              value={pending?.app?.background_update_interval_minute ?? ''}
              onChange={(e) =>
                setField(
                  ['app', 'background_update_interval_minute'],
                  e.target.value === '' ? null : Number(e.target.value)
                )
              }
            />
          </Field>
          <Field label="Cleanup Retention (days)">
            <input
              className="input"
              type="number"
              min={0}
              value={pending?.app?.post_cleanup_retention_days ?? ''}
              onChange={(e) =>
                setField(
                  ['app', 'post_cleanup_retention_days'],
                  e.target.value === '' ? null : Number(e.target.value)
                )
              }
            />
          </Field>
          <Field label="Auto-whitelist new episodes">
            <input
              type="checkbox"
              checked={!!pending?.app?.automatically_whitelist_new_episodes}
              onChange={(e) =>
                setField(['app', 'automatically_whitelist_new_episodes'], e.target.checked)
              }
            />
          </Field>
          <Field label="List all episodes in RSS and queue processing on download attempt if not previously whitelisted">
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
              <input
                type="checkbox"
                checked={!!pending?.app?.autoprocess_on_download}
                onChange={(e) => setField(['app', 'autoprocess_on_download'], e.target.checked)}
              />
            </label>
          </Field>
          <Field label="Number of episodes to whitelist from new feed archive">
            <input
              className="input"
              type="number"
              value={pending?.app?.number_of_episodes_to_whitelist_from_archive_of_new_feed ?? 1}
              onChange={(e) =>
                setField(
                  ['app', 'number_of_episodes_to_whitelist_from_archive_of_new_feed'],
                  Number(e.target.value)
                )
              }
            />
          </Field>
          <div className="col-span-1 md:col-span-2 flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 font-medium">
              <input
                type="checkbox"
                checked={!!pending?.app?.enable_public_landing_page}
                onChange={(e) => setField(['app', 'enable_public_landing_page'], e.target.checked)}
              />
              Enable the public landing page
            </label>
          </div>
        </div>
      </Section>

      <Section title="Podcast Recommendations">
        <Field label="Tavily API Key (enables AI-powered podcast recommendations)">
          <input
            className="input"
            type="password"
            placeholder={pending?.app?.tavily_api_key_preview ?? 'Enter Tavily API key…'}
            value={tavilyKeyInput}
            onChange={(e) => {
              setTavilyKeyInput(e.target.value);
              setField(['app', 'tavily_api_key'], e.target.value || null);
            }}
            autoComplete="off"
          />
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Get a free key at{' '}
            <a
              href="https://tavily.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              tavily.com
            </a>
            . Can also be set via the <code>TAVILY_API_KEY</code> environment variable.
          </p>
        </Field>
      </Section>

      <SaveButton onSave={handleSave} isPending={isSaving} />

      <style>{`.input{width:100%;padding:0.5rem;border:1px solid #e5e7eb;border-radius:0.375rem;font-size:0.875rem}.dark .input{background-color:#111827;border-color:#374151;color:#fff}`}</style>
    </div>
  );
}
