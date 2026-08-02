using System.Text.Json;
using Windows.Security.Credentials;

namespace FocusFloat.Windows;

internal sealed class ConnectionStore
{
    private const string CredentialResource = "FocusWith.FocusFloat.Windows";
    private const string CredentialUser = "focus-api-token";
    private readonly string _settingsPath;

    public ConnectionStore()
    {
        var directory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "FocusWith",
            "FocusFloat");
        Directory.CreateDirectory(directory);
        _settingsPath = Path.Combine(directory, "settings.json");
    }

    public async Task<Uri?> LoadServerUrlAsync()
    {
        if (!File.Exists(_settingsPath))
        {
            return null;
        }
        try
        {
            await using var stream = File.OpenRead(_settingsPath);
            var settings = await JsonSerializer.DeserializeAsync<ConnectionSettings>(stream);
            return Uri.TryCreate(settings?.ServerUrl, UriKind.Absolute, out var uri) ? uri : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    public string? LoadToken()
    {
        try
        {
            var vault = new PasswordVault();
            var credential = vault.Retrieve(CredentialResource, CredentialUser);
            credential.RetrievePassword();
            return credential.Password;
        }
        catch
        {
            return null;
        }
    }

    public async Task SaveAsync(Uri serverUrl, string token)
    {
        await using (var stream = File.Create(_settingsPath))
        {
            await JsonSerializer.SerializeAsync(
                stream,
                new ConnectionSettings(serverUrl.ToString()),
                new JsonSerializerOptions { WriteIndented = true });
        }

        var vault = new PasswordVault();
        try
        {
            var existing = vault.Retrieve(CredentialResource, CredentialUser);
            vault.Remove(existing);
        }
        catch
        {
            // No previous credential.
        }
        vault.Add(new PasswordCredential(CredentialResource, CredentialUser, token));
    }

    private sealed record ConnectionSettings(string ServerUrl);
}
