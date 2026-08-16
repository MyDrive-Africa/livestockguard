import { useState, useCallback } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { apiClient } from '@/api/client';
import { PageTransition } from '@/components/motion';

interface CsvRow {
  name: string;
  tag_id: string;
  species: string;
  breed: string;
  gender: string;
  colour: string;
  description: string;
  date_of_birth: string;
  weight_kg: string;
}

interface ImportResult {
  imported: number;
  skipped: number;
  errors: string[];
}

function parseCsv(text: string): { rows: CsvRow[]; errors: string[] } {
  const lines = text.split(/\r?\n/).filter(line => line.trim());
  if (lines.length < 2) {
    return { rows: [], errors: ['CSV must have a header row and at least one data row'] };
  }

  const headerLine = lines[0].toLowerCase().replace(/["\s]/g, '');
  const headers = headerLine.split(',');
  const errors: string[] = [];

  // Validate headers
  const nameIdx = headers.indexOf('name');
  const tagIdx = headers.indexOf('tag_id');
  if (nameIdx === -1 || tagIdx === -1) {
    errors.push('CSV must contain "name" and "tag_id" columns');
    return { rows: [], errors };
  }

  const rows: CsvRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(',').map(v => v.replace(/^"|"$/g, '').trim());
    if (values.length < 2) continue;

    const row: CsvRow = {
      name: values[headers.indexOf('name')] || '',
      tag_id: values[headers.indexOf('tag_id')] || '',
      species: values[headers.indexOf('species')] || 'cattle',
      breed: values[headers.indexOf('breed')] || '',
      gender: values[headers.indexOf('gender')] || '',
      colour: values[headers.indexOf('colour')] || values[headers.indexOf('color')] || '',
      description: values[headers.indexOf('description')] || '',
      date_of_birth: values[headers.indexOf('date_of_birth')] || '',
      weight_kg: values[headers.indexOf('weight_kg')] || '',
    };

    if (row.name && row.tag_id) {
      rows.push(row);
    } else {
      errors.push(`Row ${i + 1}: missing name or tag_id`);
    }
  }

  return { rows, errors };
}

export default function ImportPage() {
  const currentFarm = useAuthStore((state) => state.currentFarm);
  const [csvText, setCsvText] = useState('');
  const [parsedRows, setParsedRows] = useState<CsvRow[]>([]);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [step, setStep] = useState<'upload' | 'preview' | 'result'>('upload');
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);

  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      setCsvText(text);
      const { rows, errors } = parseCsv(text);
      setParsedRows(rows);
      setParseErrors(errors);
      setStep('preview');
    };
    reader.readAsText(file);
  }, []);

  const handlePasteImport = () => {
    const { rows, errors } = parseCsv(csvText);
    setParsedRows(rows);
    setParseErrors(errors);
    setStep('preview');
  };

  const handleConfirmImport = async () => {
    if (!currentFarm || parsedRows.length === 0) return;
    setImporting(true);

    try {
      const payload = {
        farm_id: currentFarm,
        animals: parsedRows.map(row => ({
          name: row.name,
          tag_id: row.tag_id,
          species: row.species || 'cattle',
          breed: row.breed || undefined,
          gender: row.gender || undefined,
          colour: row.colour || undefined,
          description: row.description || undefined,
          date_of_birth: row.date_of_birth || undefined,
          weight_kg: row.weight_kg ? parseFloat(row.weight_kg) : undefined,
        })),
      };

      const resp = await apiClient.post('/api/v1/animals/import/csv', payload);
      setResult(resp.data);
      setStep('result');
    } catch (err: any) {
      setResult({
        imported: 0,
        skipped: parsedRows.length,
        errors: [err.response?.data?.detail || 'Import failed'],
      });
      setStep('result');
    } finally {
      setImporting(false);
    }
  };

  const reset = () => {
    setCsvText('');
    setParsedRows([]);
    setParseErrors([]);
    setResult(null);
    setStep('upload');
  };

  return (
    <PageTransition className="p-6 h-full overflow-y-auto bg-gray-50 dark:bg-gray-900">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Import Animals (CSV)</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Bulk import cattle from a CSV file. Required columns: name, tag_id
          </p>
        </div>

        {/* Step: Upload */}
        {step === 'upload' && (
          <div className="space-y-6">
            {/* File Upload */}
            <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Upload CSV File</h2>
              <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors">
                <span className="text-4xl mb-2">📄</span>
                <span className="text-sm text-gray-500 dark:text-gray-400">Click to select CSV file</span>
                <input type="file" accept=".csv" onChange={handleFileUpload} className="hidden" />
              </label>
            </div>

            {/* Or Paste */}
            <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Or Paste CSV Data</h2>
              <textarea
                value={csvText}
                onChange={(e) => setCsvText(e.target.value)}
                placeholder={`name,tag_id,breed,gender,colour,weight_kg\nBella,LV-001,Nguni,female,Brown,420\nMax,LV-002,Brahman,male,White,550`}
                rows={8}
                className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 font-mono text-sm"
              />
              <button
                onClick={handlePasteImport}
                disabled={!csvText.trim()}
                className="mt-3 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
              >
                Parse CSV
              </button>
            </div>

            {/* Expected Format */}
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl p-4 border border-blue-200 dark:border-blue-800">
              <h3 className="text-sm font-medium text-blue-800 dark:text-blue-300 mb-2">Expected CSV Format</h3>
              <code className="text-xs text-blue-700 dark:text-blue-400 block whitespace-pre">
{`name,tag_id,species,breed,gender,colour,description,date_of_birth,weight_kg
Bella,LV-2025-001,cattle,Nguni,female,Brown and white,,2022-03-15,420
Max,LV-2025-002,cattle,Brahman,male,White,Lead bull,2020-06-01,580`}
              </code>
            </div>
          </div>
        )}

        {/* Step: Preview */}
        {step === 'preview' && (
          <div className="space-y-4">
            {parseErrors.length > 0 && (
              <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-xl p-4 border border-yellow-200 dark:border-yellow-800">
                <h3 className="text-sm font-medium text-yellow-800 dark:text-yellow-300">Parse Warnings</h3>
                <ul className="mt-2 text-xs text-yellow-700 dark:text-yellow-400 space-y-1">
                  {parseErrors.map((err, i) => <li key={i}>{err}</li>)}
                </ul>
              </div>
            )}

            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Preview ({parsedRows.length} animals)
                </h2>
                <div className="flex gap-3">
                  <button onClick={reset} className="px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg">
                    Back
                  </button>
                  <button
                    onClick={handleConfirmImport}
                    disabled={importing || parsedRows.length === 0}
                    className="px-4 py-1.5 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
                  >
                    {importing ? 'Importing...' : `Import ${parsedRows.length} Animals`}
                  </button>
                </div>
              </div>
              <div className="overflow-x-auto max-h-96">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-900 sticky top-0">
                    <tr>
                      <th className="px-4 py-2 text-left text-gray-600 dark:text-gray-400">#</th>
                      <th className="px-4 py-2 text-left text-gray-600 dark:text-gray-400">Name</th>
                      <th className="px-4 py-2 text-left text-gray-600 dark:text-gray-400">Tag ID</th>
                      <th className="px-4 py-2 text-left text-gray-600 dark:text-gray-400">Breed</th>
                      <th className="px-4 py-2 text-left text-gray-600 dark:text-gray-400">Gender</th>
                      <th className="px-4 py-2 text-left text-gray-600 dark:text-gray-400">Colour</th>
                      <th className="px-4 py-2 text-left text-gray-600 dark:text-gray-400">Weight</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {parsedRows.slice(0, 50).map((row, i) => (
                      <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                        <td className="px-4 py-2 text-gray-400">{i + 1}</td>
                        <td className="px-4 py-2 text-gray-900 dark:text-white font-medium">{row.name}</td>
                        <td className="px-4 py-2 text-gray-600 dark:text-gray-400 font-mono">{row.tag_id}</td>
                        <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{row.breed || '—'}</td>
                        <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{row.gender || '—'}</td>
                        <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{row.colour || '—'}</td>
                        <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{row.weight_kg || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {parsedRows.length > 50 && (
                  <p className="px-4 py-2 text-xs text-gray-400">Showing first 50 of {parsedRows.length} rows</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Step: Result */}
        {step === 'result' && result && (
          <div className="space-y-4">
            <div className={`rounded-xl p-6 border ${result.imported > 0 ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'}`}>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                {result.imported > 0 ? '✅ Import Complete' : '❌ Import Failed'}
              </h2>
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-600">{result.imported}</p>
                  <p className="text-xs text-gray-500">Imported</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-yellow-600">{result.skipped}</p>
                  <p className="text-xs text-gray-500">Skipped</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-red-600">{result.errors.length}</p>
                  <p className="text-xs text-gray-500">Errors</p>
                </div>
              </div>
              {result.errors.length > 0 && (
                <ul className="text-xs text-red-600 dark:text-red-400 space-y-1 max-h-40 overflow-y-auto">
                  {result.errors.map((err, i) => <li key={i}>{err}</li>)}
                </ul>
              )}
            </div>
            <button onClick={reset} className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700">
              Import More
            </button>
          </div>
        )}
      </div>
    </PageTransition>
  );
}
